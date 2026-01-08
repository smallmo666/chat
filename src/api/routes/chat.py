import asyncio
import json
import uuid
import time
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Union
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from src.workflow.graph import create_graph
from src.core.database import get_app_db
from src.core.models import AuditLog, User, ChatSession
from src.utils.callbacks import UIStreamingCallbackHandler
from src.api.schemas import (
    ChatRequest,
    SessionListRequest,
    SessionHistoryRequest,
    SessionUpdateRequest,
    SessionDeleteRequest
)
# Import auth dependency
from src.core.security_auth import get_current_active_user
from src.core.event_bus import EventBus
from sqlmodel import select

router = APIRouter(tags=["chat"])

# Initialize Graph lazily or globally
_graph_app = None

def get_graph():
    global _graph_app
    if not _graph_app:
        print("Initializing Graph...")
        _graph_app = create_graph()
    return _graph_app

async def event_generator(
    message: str, 
    selected_tables: Optional[list[str]], 
    thread_id: str, 
    project_id: Optional[int],
    user_id: Optional[int],
    command: str = "start",
    modified_sql: Optional[Union[str, dict]] = None,
    clarify_choices: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    """
    生成器，用于生成来自图状态更新和 LLM 令牌流（通过回调）的 SSE 事件。
    """
    queue = asyncio.Queue()
    # 关键：设置当前请求的 queue 到 EventBus
    EventBus.set_queue(queue)
    
    SENTINEL = object()
    
    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        main_loop = asyncio.new_event_loop()
    
    def token_callback(text: str):
        main_loop.call_soon_threadsafe(queue.put_nowait, {"type": "thinking", "content": text})

    async def run_graph():
        try:
            graph_app = get_graph()
            
            # 关键修改: 将 user_id 注入到 configurable 中，供 ClarifyIntent 等节点使用
            config = {
                "configurable": {
                    "thread_id": thread_id, 
                    "project_id": project_id,
                    "user_id": user_id 
                },
                "recursion_limit": 100,
                "callbacks": [UIStreamingCallbackHandler(token_callback)]
            }
            
            inputs = None
            
            if command == "start":
                inputs = {
                    "messages": [HumanMessage(content=message)],
                    "manual_selected_tables": selected_tables,
                    # Clear previous turn's context to prevent state pollution
                    "rewritten_query": None,
                    "plan": None,
                    "current_step_index": 0,
                    "intent_clear": True,
                    "dsl": None,
                    "sql": None,
                    "results": None,
                    "error": None,
                    "relevant_schema": None,
                    "visualization": None,
                    "python_code": None,
                    "analysis": None,
                    "insights": None,
                    "ui_component": None,
                    "hypotheses": None,
                    "knowledge_context": None,
                    "next": "START" # Reset next step
                }
            elif command == "edit":
                # Check if state exists before resuming
                snapshot = await graph_app.aget_state(config)
                if not snapshot.values:
                    await queue.put({"type": "error", "content": "会话已过期或状态丢失，请刷新页面重新开始。"})
                    return

                if modified_sql:
                    await graph_app.aupdate_state(config, {"sql": modified_sql}, as_node="DSLtoSQL")
                inputs = None # Resume
            elif command == "approve":
                # Check if state exists before resuming
                snapshot = await graph_app.aget_state(config)
                if not snapshot.values:
                    await queue.put({"type": "error", "content": "会话已过期或状态丢失，请刷新页面重新开始。"})
                    return
                # Ensure we resume execution by passing None inputs, but we might need to explicitly tell it to proceed
                # In LangGraph 0.2+, if paused at interrupt, resuming with None should continue to next node.
                # However, if state is stale, we might need to verify next node.
                if not snapshot.next:
                     print("DEBUG: No next node found in snapshot, forcing resume")
                     
                inputs = None # Resume
            elif command == "clarify":
                snapshot = await graph_app.aget_state(config)
                if not snapshot.values:
                    await queue.put({"type": "error", "content": "会话已过期或状态丢失，请刷新页面重新开始。"})
                    return
                prev_msgs = snapshot.values.get("messages", [])
                new_msgs = prev_msgs + ([HumanMessage(content=message)] if message else [])
                retry = int(snapshot.values.get("clarify_retry_count", 0) or 0) + 1
                
                update_payload = {
                    "messages": new_msgs,
                    "clarify_pending": False,
                    "clarify_retry_count": retry
                }
                
                # Handle modified_sql being a dictionary (e.g. clarify choices passed as sql)
                # or a string (actual SQL edit)
                if modified_sql:
                    if isinstance(modified_sql, dict):
                        # Extract choices if present
                        if "clarify_choices" in modified_sql:
                            update_payload["clarify_answer"] = {"choices": modified_sql["clarify_choices"]}
                            update_payload["intent_clear"] = True
                    else:
                        update_payload["sql"] = modified_sql
                        update_payload["intent_clear"] = True # Assume manual SQL fixes intent
                elif clarify_choices:
                    update_payload["clarify_answer"] = {"choices": clarify_choices}
                    update_payload["intent_clear"] = True
                    
                await graph_app.aupdate_state(config, update_payload, as_node="ClarifyIntent")
                inputs = None
            
            step_start_time = time.time()
            
            # Audit Log Data Accumulator (Initialize with default or load from history if needed)
            audit_data = {
                "project_id": project_id,
                "user_id": user_id, # Record User ID
                "session_id": thread_id,
                "user_query": message,
                "plan": [],
                "executed_sql": None,
                "generated_dsl": None, # 初始化 DSL
                "result_summary": None,
                "status": "success", 
                "error_message": None,
                "start_time": time.time()
            }
            
            # Use stream_mode="updates" to get incremental updates
            async for output in graph_app.astream(inputs, config=config):
                # Check cancellation (though astream handles it, we want to be explicit for audit)
                if queue.empty() and False: # Placeholder for cancellation check if needed
                    break

                step_end_time = time.time()
                duration = round((step_end_time - step_start_time) * 1000)
                step_start_time = step_end_time
                
                for node_name, state_update in output.items():
                    if node_name == "Supervisor": continue
                        
                    event_data = {
                        "type": "step",
                        "node": node_name,
                        "status": "completed",
                        "details": "",
                        "duration": duration
                    }
                    
                    # 仍然调用动态生成器，作为节点完成后的补充（或移除，避免重复）
                    # 鉴于我们已经在 Node 内部做了实时推送，这里的“事后”推送可以作为一种状态同步或保留 high 粒度指标
                    try:
                        from src.workflow.utils.substeps import build_substeps
                        subs = build_substeps(node_name, state_update, verbosity="medium")
                        for s in subs:
                            await queue.put({"type": "substep", **s})
                    except Exception:
                        pass
                    
                    if node_name == "DataDetective":
                        hypotheses = state_update.get("hypotheses", [])
                        depth = state_update.get("analysis_depth", "simple")
                        
                        event_data["details"] = f"分析完成 (模式: {depth})"
                        if hypotheses:
                             # 发送专门的侦探洞察事件
                             await queue.put({
                                 "type": "detective_insight", 
                                 "hypotheses": hypotheses,
                                 "depth": depth
                             })
                             # 同时发送一条 AIMessage 结果给前端展示
                             msgs = state_update.get("messages", [])
                             if msgs and isinstance(msgs[-1], AIMessage):
                                 await queue.put({"type": "result", "content": msgs[-1].content})

                    elif node_name == "Planner":
                        plan = state_update.get("plan", [])
                        await queue.put({"type": "plan", "content": plan})
                        event_data["details"] = f"已生成 {len(plan)} 步执行计划"
                        audit_data["plan"] = plan
                        

                    elif node_name == "ClarifyIntent":
                        intent_clear = state_update.get("intent_clear", False)
                        event_data["details"] = "意图清晰" if intent_clear else "需要澄清"
                        # 澄清逻辑已在 Node 内部处理，这里主要处理其他状态或日志
                        if not intent_clear:
                             audit_data["status"] = "clarification_needed"
                             # 兼容性：如果 Node 内部发送失败或为了确保前端收到，再次检查
                             # 但如果 Node 内部已发，这里可能会发两次。前端应去重或更新
                             # 鉴于 Node 内部的 emit 更可靠且实时，这里可以简化
                             pass 
                        else:
                            pass

                    elif node_name == "SelectTables":
                        # 处理歧义情况
                        if state_update.get("intent_clear") is False:
                             msgs = state_update.get("messages", [])
                             if msgs and isinstance(msgs[-1], AIMessage):
                                 await queue.put({"type": "result", "content": msgs[-1].content})
                                 audit_data["status"] = "clarification_needed"
                                 # 同样，SelectTables 的歧义处理最好也移到 Node 内部
                            
                        else:
                            schema = state_update.get("relevant_schema", "")
                            display_schema = schema[:100] + "..." if len(schema) > 100 else schema
                            event_data["details"] = "已选择相关表:\n" + display_schema
                            
                            import re
                            extracted_tables = []
                            for line in schema.split('\n'):
                                if line.startswith("表名:"):
                                    match = re.match(r"表名:\s*(\w+)", line)
                                    if match:
                                        extracted_tables.append(match.group(1))
                            
                            if extracted_tables:
                                await queue.put({"type": "selected_tables", "content": extracted_tables})
                            

                    elif node_name == "GenerateDSL":
                        dsl = state_update.get("dsl", "")
                        event_data["details"] = dsl
                        audit_data["generated_dsl"] = dsl # 捕获 DSL
                        
                        
                    elif node_name == "DSLtoSQL":
                        sql = state_update.get("sql", "")
                        event_data["details"] = sql
                        audit_data["executed_sql"] = sql
                        
                        
                    elif node_name == "ExecuteSQL":
                        results_json_str = state_update.get("results", "[]")
                        event_data["details"] = "查询成功"
                        # 仅当结果看起来是 JSON 数组时再解析导出
                        if isinstance(results_json_str, str) and results_json_str.strip().startswith("["):
                            try:
                                json_data = json.loads(results_json_str)
                                row_count = len(json_data) if isinstance(json_data, list) else 0
                                audit_data["result_summary"] = f"Returned {row_count} rows"
                                if isinstance(json_data, list) and len(json_data) > 0:
                                    await queue.put({"type": "data_export", "content": json_data})
                            except Exception as e:
                                print(f"Failed to parse results JSON for export: {e}")
                        token = state_update.get("download_token")
                        if token:
                            await queue.put({"type": "data_download", "content": token})

                        msgs = state_update.get("messages", [])
                        if msgs and isinstance(msgs[-1], AIMessage):
                            await queue.put({"type": "result", "content": msgs[-1].content})

                    elif node_name == "PythonAnalysis":
                        # 处理 Python 代码执行节点
                        code = state_update.get("python_code", "")
                        analysis = state_update.get("analysis", "")
                        ui_images = state_update.get("ui_images", []) # Get images from state
                        
                        if code:
                             # 增加一个新的事件类型 'code_generated'
                             await queue.put({"type": "code_generated", "content": code})
                        
                        # Send images if available
                        if ui_images:
                            await queue.put({"type": "python_images", "content": ui_images})
                        
                        if analysis:
                            event_data["details"] = "高级分析完成"
                            await queue.put({"type": "analysis", "content": analysis})
                        else:
                             msgs = state_update.get("messages", [])
                             if msgs and isinstance(msgs[-1], AIMessage):
                                 await queue.put({"type": "result", "content": msgs[-1].content})

                    elif node_name == "Visualization":
                        viz = state_update.get("visualization", {})
                        event_data["details"] = "可视化生成完成"
                        if viz:
                            await queue.put({"type": "visualization_config", "content": viz})
                            # Also send old visualization event for backward compatibility if needed, 
                            # but UIArtist uses config now.
                            # Let's keep sending 'visualization' as well if it contains options
                            await queue.put({"type": "visualization", "content": viz})
                        else:
                            msgs = state_update.get("messages", [])
                            if msgs and isinstance(msgs[-1], AIMessage):
                                await queue.put({"type": "result", "content": msgs[-1].content})

                    elif node_name == "InsightMiner":
                        # 处理 InsightMiner 的结果
                        insights = state_update.get("insights", [])
                        event_data["details"] = f"挖掘到 {len(insights)} 条洞察"
                        if insights:
                            await queue.put({"type": "insight_mined", "content": insights})

                    elif node_name == "UIArtist":
                        # 处理 UIArtist 的结果
                        ui_component = state_update.get("ui_component", "")
                        event_data["details"] = "UI 组件已生成"
                        if ui_component:
                            await queue.put({"type": "ui_generated", "content": ui_component})

                    elif node_name == "TableQA":
                        msgs = state_update.get("messages", [])
                        if msgs and isinstance(msgs[-1], AIMessage):
                            await queue.put({"type": "result", "content": msgs[-1].content})

                    await queue.put(event_data)
            
            # Check for Interrupts
            snapshot = await graph_app.aget_state(config)
            if snapshot.next and "ExecuteSQL" in snapshot.next:
                # We are paused before ExecuteSQL
                current_sql = snapshot.values.get("sql", "")
                await queue.put({"type": "interrupt", "content": current_sql})
                # Do not save audit log yet, as we are not done (or save as 'pending')
                # For simplicity, we skip saving here and wait for approval flow
                return 

            # Save Audit Log (Success)
            try:
                total_duration = round((time.time() - audit_data["start_time"]) * 1000)
                app_db = get_app_db()
                with app_db.get_session() as session:
                    # Update session
                    chat_session = session.get(ChatSession, thread_id)
                    if chat_session:
                        chat_session.updated_at = datetime.utcnow()
                        session.add(chat_session)
                    
                    # Create audit log
                    log = AuditLog(
                        project_id=project_id,
                        user_id=user_id,
                        session_id=thread_id,
                        user_query=message,
                        plan={"steps": audit_data.get("plan", [])} if isinstance(audit_data.get("plan"), list) else audit_data.get("plan"),
                        executed_sql=audit_data.get("executed_sql"),
                        generated_dsl=audit_data.get("generated_dsl"),
                        result_summary=audit_data.get("result_summary"),
                        duration_ms=total_duration,
                        status=audit_data.get("status", "success"),
                        error_message=None
                    )
                    session.add(log)
                    session.commit()
                    
                    # Feedback trigger?
                    # await queue.put({"type": "feedback_request", "audit_id": log.id})
            except Exception as e:
                print(f"Failed to save audit log: {e}")

        except Exception as e:
            await queue.put({"type": "error", "content": str(e)})
            # Audit log (Error)
            try:
                app_db = get_app_db()
                with app_db.get_session() as session:
                    log = AuditLog(
                        project_id=project_id,
                        user_id=user_id,
                        session_id=thread_id,
                        user_query=message,
                        status="error",
                        error_message=str(e),
                        duration_ms=0
                    )
                    session.add(log)
                    session.commit()
            except:
                pass
        finally:
            await queue.put(SENTINEL)

    asyncio.create_task(run_graph())

    while True:
        item = await queue.get()
        if item is SENTINEL:
            break
        yield f"event: {item['type']}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
        queue.task_done()

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user) # Protected Route
):
    thread_id = request.thread_id or str(uuid.uuid4())
    
    # Session Management: Upsert Session
    if request.project_id:
        app_db = get_app_db()
        try:
            with app_db.get_session() as session:
                chat_session = session.get(ChatSession, thread_id)
                if not chat_session:
                    # Create new session
                    # Auto-generate title from first few words of message
                    title = request.message[:20] + "..." if len(request.message) > 20 else request.message
                    if not title.strip():
                        title = "新会话"
                        
                    chat_session = ChatSession(
                        id=thread_id,
                        user_id=current_user.id,
                        project_id=request.project_id,
                        title=title
                    )
                    session.add(chat_session)
                else:
                    # Update timestamp
                    chat_session.updated_at = datetime.utcnow()
                    session.add(chat_session)
                session.commit()
        except Exception as e:
            print(f"Error managing session: {e}")
            # Non-blocking, continue chat
    
    return StreamingResponse(
        event_generator(
            request.message, 
            request.selected_tables, 
            thread_id, 
            request.project_id,
            current_user.id, # Pass current user ID
            request.command,
            request.modified_sql,
            request.clarify_choices # Pass clarify choices
        ),
        media_type="text/event-stream"
    )

@router.post("/chat/sessions/list")
def list_sessions(
    req: SessionListRequest,
    current_user: User = Depends(get_current_active_user)
):
    
    if req.project_id is None:
        return []

    app_db = get_app_db()
    with app_db.get_session() as session:
        rows = session.exec(
            select(ChatSession)
            .where(
                ChatSession.user_id == current_user.id,
                ChatSession.project_id == req.project_id,
                ChatSession.is_active == True
            )
            .order_by(ChatSession.updated_at.desc())
        ).all()
        return rows

@router.post("/chat/sessions/history")
def session_history(
    req: SessionHistoryRequest,
    current_user: User = Depends(get_current_active_user)
):
    app_db = get_app_db()
    with app_db.get_session() as session:
        logs = session.exec(
            select(AuditLog)
            .where(
                AuditLog.session_id == req.session_id,
                AuditLog.user_id == current_user.id
            )
            .order_by(AuditLog.created_at.desc())
        ).all()
        return logs

@router.post("/chat/sessions/update")
def update_session_title(
    req: SessionUpdateRequest,
    current_user: User = Depends(get_current_active_user)
):
    app_db = get_app_db()
    with app_db.get_session() as session:
        s = session.get(ChatSession, req.session_id)
        if not s or s.user_id != current_user.id:
            return {"success": False}
        s.title = req.title.strip() or s.title
        s.updated_at = datetime.utcnow()
        session.add(s)
        session.commit()
        return {"success": True}

@router.post("/chat/sessions/delete")
def delete_session(
    req: SessionDeleteRequest,
    current_user: User = Depends(get_current_active_user)
):
    app_db = get_app_db()
    with app_db.get_session() as session:
        s = session.get(ChatSession, req.session_id)
        if not s or s.user_id != current_user.id:
            return {"success": False}
        s.is_active = False
        s.updated_at = datetime.utcnow()
        session.add(s)
        session.commit()
        return {"success": True}
