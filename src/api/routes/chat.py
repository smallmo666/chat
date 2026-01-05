import asyncio
import json
import uuid
import time
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from src.workflow.graph import create_graph
from src.core.database import get_app_db
from src.core.models import AuditLog, User
from src.utils.callbacks import UIStreamingCallbackHandler
from src.api.schemas import ChatRequest
# Import auth dependency
from src.core.security_auth import get_current_active_user

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
            
            config = {
                "configurable": {"thread_id": thread_id, "project_id": project_id},
                "recursion_limit": 50,
                "callbacks": [UIStreamingCallbackHandler(token_callback)]
            }
            
            inputs = None
            
            if command == "start":
                inputs = {
                    "messages": [HumanMessage(content=message)],
                    "manual_selected_tables": selected_tables
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
                        except Exception as e:
                            print(f"Failed to parse results JSON for export: {e}")

                        msgs = state_update.get("messages", [])
                        if msgs and isinstance(msgs[-1], AIMessage):
                            await queue.put({"type": "result", "content": msgs[-1].content})

                    elif node_name == "PythonAnalysis":
                        # 处理 Python 代码执行节点
                        code = state_update.get("python_code", "")
                        analysis = state_update.get("analysis", "")
                        
                        if code:
                             # 增加一个新的事件类型 'code_generated'
                             await queue.put({"type": "code_generated", "content": code})
                        
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
                        error_message=str(e)
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

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user) # Protected Route
):
    thread_id = request.thread_id or str(uuid.uuid4())
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
