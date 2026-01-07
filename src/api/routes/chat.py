import asyncio
import json
import uuid
import time
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from src.workflow.graph import create_graph
from src.core.database import get_app_db
from src.core.models import AuditLog, User, Knowledge, Dashboard, ChatSession
from src.utils.callbacks import UIStreamingCallbackHandler
from src.api.schemas import (
    ChatRequest, 
    PythonExecRequest, 
    SessionListRequest, 
    SessionHistoryRequest, 
    SessionDeleteRequest, 
    SessionUpdateRequest
)
# Import auth dependency
from src.core.security_auth import get_current_active_user
from sqlmodel import select, desc

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
    user_id: Optional[int], # Added user_id
    command: str = "start",
    modified_sql: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    生成器，用于生成来自图状态更新和 LLM 令牌流（通过回调）的 SSE 事件。
    """
    queue = asyncio.Queue()
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
                "recursion_limit": 50,
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
                    "intent_clear": False,
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
                    await graph_app.aupdate_state(config, {"sql": modified_sql})
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
                        if not intent_clear:
                             msgs = state_update.get("messages", [])
                             if msgs and isinstance(msgs[-1], AIMessage):
                                 await queue.put({"type": "result", "content": msgs[-1].content})
                                 audit_data["status"] = "clarification_needed"

                    elif node_name == "SelectTables":
                        # 处理歧义情况
                        if state_update.get("intent_clear") is False:
                             msgs = state_update.get("messages", [])
                             if msgs and isinstance(msgs[-1], AIMessage):
                                 await queue.put({"type": "result", "content": msgs[-1].content})
                                 audit_data["status"] = "clarification_needed"
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
                        try:
                            json_data = json.loads(results_json_str)
                            row_count = len(json_data) if isinstance(json_data, list) else 0
                            audit_data["result_summary"] = f"Returned {row_count} rows"
                            if isinstance(json_data, list) and len(json_data) > 0:
                                await queue.put({"type": "data_export", "content": json_data})
                            token = state_update.get("download_token")
                            if token:
                                await queue.put({"type": "data_download", "content": token})
                        except Exception as e:
                            print(f"Failed to parse results JSON for export: {e}")

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
                    log_entry = AuditLog(
                        project_id=audit_data["project_id"],
                        user_id=audit_data["user_id"], # Save user_id
                        session_id=audit_data["session_id"],
                        user_query=audit_data["user_query"],
                        plan=audit_data["plan"],
                        executed_sql=audit_data["executed_sql"],
                        generated_dsl=audit_data["generated_dsl"], # 保存 DSL
                        result_summary=audit_data["result_summary"],
                        duration_ms=total_duration,
                        status=audit_data["status"],
                        error_message=audit_data["error_message"]
                    )
                    session.add(log_entry)
                    session.commit()
            except Exception as e:
                print(f"Failed to save audit log: {e}")
                    
        except GeneratorExit:
            print(f"Client disconnected from stream: {thread_id}")
            # Save Audit Log (Cancelled)
            try:
                total_duration = round((time.time() - audit_data.get("start_time", time.time())) * 1000)
                app_db = get_app_db()
                with app_db.get_session() as session:
                    log_entry = AuditLog(
                        project_id=audit_data.get("project_id"),
                        user_id=audit_data.get("user_id"),
                        session_id=audit_data.get("session_id", "unknown"),
                        user_query=audit_data.get("user_query", ""),
                        plan=audit_data.get("plan"),
                        executed_sql=audit_data.get("executed_sql"),
                        generated_dsl=audit_data.get("generated_dsl"), # 保存 DSL
                        result_summary="Cancelled",
                        duration_ms=total_duration,
                        status="cancelled",
                        error_message="Client disconnected"
                    )
                    session.add(log_entry)
                    session.commit()
            except Exception as log_err:
                print(f"Failed to save cancelled audit log: {log_err}")
            raise # Re-raise to stop generator properly

        except Exception as e:
            # Save Audit Log (Error)
            try:
                total_duration = round((time.time() - audit_data.get("start_time", time.time())) * 1000)
                app_db = get_app_db()
                with app_db.get_session() as session:
                    log_entry = AuditLog(
                        project_id=audit_data.get("project_id"),
                        user_id=audit_data.get("user_id"),
                        session_id=audit_data.get("session_id", "unknown"),
                        user_query=audit_data.get("user_query", ""),
                        plan=audit_data.get("plan"),
                        executed_sql=audit_data.get("executed_sql"),
                        generated_dsl=audit_data.get("generated_dsl"), # 保存 DSL
                        result_summary="Error",
                        duration_ms=total_duration,
                        status="error",
                        error_message=str(e)[:2000]
                    )
                    session.add(log_entry)
                    session.commit()
            except Exception as log_err:
                print(f"Failed to save error audit log: {log_err}")

            await queue.put({"type": "error", "content": str(e)})
            import traceback
            traceback.print_exc()
        finally:
            await queue.put(SENTINEL)

    asyncio.create_task(run_graph())
    
    while True:
        data = await queue.get()
        if data is SENTINEL:
            break
        yield f"event: {data['type']}\n"
        yield f"data: {json.dumps(data)}\n\n"

@router.post("/chat/python/execute")
async def execute_python_code(
    request: PythonExecRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Execute Python code in the context of an existing project session.
    """
    # Use project_id as session_id to reuse the DataFrame context
    sandbox = StatefulSandbox(session_id=request.project_id)
    
    # Execute code
    # We don't pass 'df' here because we assume it's already in the session's locals
    # from previous 'PythonAnalysis' node execution.
    # However, if the session expired or 'df' is missing, the user might get a NameError.
    # Ideally, we should check if 'df' exists, or the UI should warn the user.
    
    result = await asyncio.to_thread(sandbox.execute, request.code)
    
    return result

@router.post("/knowledge")
async def add_knowledge(
    term: str,
    definition: str,
    formula: Optional[str] = None,
    tags: Optional[list[str]] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    添加业务知识条目
    """
    # TODO: In future, integrate with Vector Store embedding
    app_db = get_app_db()
    with app_db.get_session() as session:
        # Check organization (assuming user belongs to one)
        # org_id = current_user.organization_id # Need to implement multi-tenancy context
        
        knowledge = Knowledge(
            term=term,
            definition=definition,
            formula=formula,
            tags=tags or []
        )
        session.add(knowledge)
        session.commit()
        session.refresh(knowledge)
        return knowledge

@router.get("/knowledge")
async def list_knowledge(
    current_user: User = Depends(get_current_active_user)
):
    app_db = get_app_db()
    with app_db.get_session() as session:
        statement = select(Knowledge).order_by(Knowledge.created_at.desc())
        results = session.exec(statement).all()
        return results

@router.delete("/knowledge/{kid}")
async def delete_knowledge(
    kid: int,
    current_user: User = Depends(get_current_active_user)
):
    app_db = get_app_db()
    with app_db.get_session() as session:
        k = session.get(Knowledge, kid)
        if not k:
            return {"error": "Not found"}
        session.delete(k)
        session.commit()
        return {"status": "deleted"}

@router.post("/dashboards")
async def create_dashboard(
    title: str,
    project_id: int,
    layout: dict = {},
    charts: list = [],
    current_user: User = Depends(get_current_active_user)
):
    app_db = get_app_db()
    with app_db.get_session() as session:
        dashboard = Dashboard(
            title=title,
            project_id=project_id,
            user_id=current_user.id,
            layout=layout,
            charts=charts
        )
        session.add(dashboard)
        session.commit()
        session.refresh(dashboard)
        return dashboard

@router.get("/dashboards")
async def list_dashboards(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user)
):
    app_db = get_app_db()
    with app_db.get_session() as session:
        query = select(Dashboard)
        if project_id:
            query = query.where(Dashboard.project_id == project_id)
        results = session.exec(query).all()
        return results

# --- Session Management Endpoints ---

@router.post("/chat/sessions/list")
async def list_sessions(
    request: SessionListRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前用户在指定项目下的会话列表。
    """
    app_db = get_app_db()
    with app_db.get_session() as session:
        query = select(ChatSession).where(
            ChatSession.user_id == current_user.id,
            ChatSession.project_id == request.project_id,
            ChatSession.is_active == True
        ).order_by(desc(ChatSession.updated_at))
        
        results = session.exec(query).all()
        return results

@router.post("/chat/sessions/history")
async def get_session_history(
    request: SessionHistoryRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取指定会话的历史消息记录 (从 LangGraph 状态恢复)。
    """
    graph_app = get_graph()
    
    # 验证 Session 是否属于该用户 (可选，但推荐)
    app_db = get_app_db()
    with app_db.get_session() as session:
        chat_session = session.get(ChatSession, request.session_id)
        if not chat_session or chat_session.user_id != current_user.id:
             # 如果找不到，或者不属于该用户，返回空或错误
             # 为了安全，这里不报错，只返回空历史
             pass 

    # 从 LangGraph 获取状态
    config = {"configurable": {"thread_id": request.session_id}}
    try:
        snapshot = await graph_app.aget_state(config)
        if not snapshot.values:
            return []
            
        messages = snapshot.values.get("messages", [])
        
        # 序列化消息
        history = []
        for msg in messages:
            msg_type = msg.type
            content = msg.content
            # 处理特殊类型的消息内容 (如 AIMessage 可能包含 tool_calls)
            history.append({
                "type": msg_type,
                "content": content
            })
            
        return history
    except Exception as e:
        print(f"Failed to fetch history for session {request.session_id}: {e}")
        return []

@router.post("/chat/sessions/delete")
async def delete_session(
    request: SessionDeleteRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    软删除会话。
    """
    app_db = get_app_db()
    with app_db.get_session() as session:
        chat_session = session.get(ChatSession, request.session_id)
        if not chat_session:
            return {"error": "Session not found"}
        
        if chat_session.user_id != current_user.id:
            return {"error": "Permission denied"}
            
        chat_session.is_active = False
        session.add(chat_session)
        session.commit()
        return {"status": "success", "session_id": request.session_id}

@router.post("/chat/sessions/update")
async def update_session(
    request: SessionUpdateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    更新会话标题。
    """
    app_db = get_app_db()
    with app_db.get_session() as session:
        chat_session = session.get(ChatSession, request.session_id)
        if not chat_session:
            return {"error": "Session not found"}
            
        if chat_session.user_id != current_user.id:
            return {"error": "Permission denied"}
            
        chat_session.title = request.title
        chat_session.updated_at = datetime.utcnow()
        session.add(chat_session)
        session.commit()
        return {"status": "success", "session_id": request.session_id, "title": request.title}

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
            request.modified_sql
        ),
        media_type="text/event-stream"
    )
