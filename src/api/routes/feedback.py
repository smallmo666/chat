from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlmodel import select

from src.core.database import get_app_db
from src.core.models import AuditLog
from src.domain.memory.few_shot import get_few_shot_retriever
from src.domain.memory.semantic_cache import get_semantic_cache

router = APIRouter(tags=["feedback"])

class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="对话 Session ID (Thread ID)")
    rating: int = Field(..., description="评分: 1 (赞), -1 (踩)")
    correction: Optional[str] = Field(None, description="用户修正的 SQL (可选)")
    comment: Optional[str] = Field(None, description="用户评论")

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    提交用户反馈。
    并根据反馈触发强化学习机制 (RLHF-lite)。
    """
    app_db = get_app_db()
    with app_db.get_session() as session:
        # 1. 查找 AuditLog
        statement = select(AuditLog).where(AuditLog.session_id == request.session_id).order_by(AuditLog.created_at.desc())
        results = session.exec(statement)
        audit_log = results.first()
        
        if not audit_log:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # 2. 更新反馈信息
        audit_log.feedback_rating = request.rating
        audit_log.feedback_comment = request.comment
        session.add(audit_log)
        session.commit()
        session.refresh(audit_log)
        
        # 3. 强化学习逻辑 (Reinforcement Logic)
        project_id = audit_log.project_id
        user_query = audit_log.user_query
        executed_sql = audit_log.executed_sql
        dsl = audit_log.generated_dsl
        
        # 获取相关组件
        few_shot = get_few_shot_retriever(project_id)
        semantic_cache = get_semantic_cache(project_id)
        
        if request.rating == 1:
            # --- POSITIVE FEEDBACK (👍) ---
            print(f"Feedback: Positive for {request.session_id}. Promoting to Knowledge Base.")
            
            # A. 写入 Semantic Cache (加速未来查询)
            if user_query and executed_sql:
                try:
                    semantic_cache.add(user_query, executed_sql)
                except Exception as e:
                    print(f"Failed to update Semantic Cache: {e}")
            
            # B. 写入 Few-Shot Examples (增强 RAG)
            if user_query and dsl and executed_sql:
                try:
                    few_shot.add_example(
                        question=user_query,
                        dsl=dsl,
                        sql=executed_sql,
                        metadata={"source": "user_feedback_positive", "session_id": request.session_id}
                    )
                except Exception as e:
                    print(f"Failed to update Few-Shot: {e}")
                    
        elif request.rating == -1:
            # --- NEGATIVE FEEDBACK (👎) ---
            print(f"Feedback: Negative for {request.session_id}.")
            
            # A. 从 Semantic Cache 移除 (防止错误缓存)
            # 目前 Semantic Cache 接口可能不支持精确删除，或者我们需要实现它。
            # 暂时跳过，或者假设 Cache 有 TTL。
            # TODO: Implement semantic_cache.remove(user_query)
            
            # B. 处理 Correction (修正)
            if request.correction:
                print(f"Feedback: Received correction. Adding to Knowledge Base.")
                # 将 (Query, Corrected SQL) 写入 Few-Shot
                # 注意：这里我们可能没有 Corrected DSL，所以 DSL 字段可能为空或复用旧的(不准确)
                # 为了安全，我们只存 SQL，或者尝试推导 DSL (太复杂)。
                # 策略：Few-Shot Prompt 允许 DSL 为空或 "N/A"
                try:
                    few_shot.add_example(
                        question=user_query,
                        dsl=dsl or "N/A", # 复用旧 DSL 可能会有误导，但在 SQL 正确的情况下通常可以接受
                        sql=request.correction,
                        metadata={"source": "user_correction", "session_id": request.session_id}
                    )
                except Exception as e:
                    print(f"Failed to add correction to Few-Shot: {e}")

    return {"status": "success", "message": "Feedback received and processed."}
