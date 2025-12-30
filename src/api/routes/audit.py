from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from src.core.database import get_app_db, AppDatabase
from src.core.models import AuditLog
from src.api.schemas import FeedbackRequest
from src.domain.memory.few_shot import get_few_shot_retriever

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/logs")
def get_audit_logs(project_id: Optional[int] = None, session_id: Optional[str] = None, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        query = select(AuditLog)
        if project_id:
            query = query.where(AuditLog.project_id == project_id)
        if session_id:
            query = query.where(AuditLog.session_id == session_id)
        logs = session.exec(query.order_by(AuditLog.created_at.desc()).limit(100)).all()
        return logs

@router.post("/feedback")
def submit_feedback(feedback: FeedbackRequest, app_db: AppDatabase = Depends(get_app_db)):
    """
    提交用户反馈，并触发自学习流程。
    """
    with app_db.get_session() as session:
        log = session.get(AuditLog, feedback.audit_id)
        if not log:
            raise HTTPException(status_code=404, detail="Audit log not found")
        
        # Update Feedback
        log.feedback_rating = feedback.rating
        log.feedback_comment = feedback.comment
        session.add(log)
        session.commit()
        session.refresh(log)
        
        # Auto-Learning: If Positive Feedback
        if feedback.rating > 0 and log.executed_sql and log.status == "success":
            try:
                # 触发 RAG 学习
                retriever = get_few_shot_retriever(log.project_id)
                retriever.add_example(
                    question=log.user_query,
                    sql=log.executed_sql,
                    metadata={
                        "source": "user_feedback", 
                        "audit_id": log.id,
                        "rating": feedback.rating
                    }
                )
                print(f"Auto-learned from feedback: Audit {log.id}")
            except Exception as e:
                print(f"Auto-learning failed: {e}")
                
        return {"ok": True, "message": "Feedback received"}
