import asyncio
import json
import uuid
import warnings
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel

from src.graph import create_graph
from src.utils.db import get_query_db, get_app_db
from src.utils.callbacks import UIStreamingCallbackHandler

# Suppress warnings
warnings.filterwarnings("ignore")

app = FastAPI(title="Text2SQL Agent API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo purposes, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global graph (will be compiled once)
graph_app = None

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
    selected_tables: Optional[list[str]] = None

@app.on_event("startup")
async def startup_event():
    global graph_app
    print("Initializing Text2SQL Agent...")
    try:
        query_db = get_query_db()
        app_db = get_app_db()
        query_db.ensure_demo_data()
        schema_info = query_db.inspect_schema()
        app_db.save_schema_info(schema_info)
        print("Database schema synced.")
    except Exception as e:
        print(f"Initialization error: {e}")
    
    graph_app = create_graph()
    print("Graph initialized.")

async def event_generator(message: str, selected_tables: Optional[list[str]], thread_id: str) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE events from both the Graph state updates
    and the LLM token stream (via callback).
    """
    queue = asyncio.Queue()
    
    # Sentinel object to signal end of stream
    SENTINEL = object()
    
    # Capture the main event loop to safely schedule callbacks from threads
    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        # Should not happen in async function, but as fallback
        main_loop = asyncio.new_event_loop()
    
    # 1. Callback for LLM tokens
    def token_callback(text: str):
        # We only push the *new* chunk if possible, but the callback handler provided
        # in src/utils/callbacks.py currently accumulates text.
        # Let's check src/utils/callbacks.py
        # It calls update_callback(self.current_text)
        # For streaming efficiency, it's better to send chunks.
        # But our UIStreamingCallbackHandler sends full text?
        # Let's assume we want to send the full text updates or chunks.
        # To minimize bandwidth, chunks are better, but full text is easier for UI to sync.
        # Let's wrap the update in a dict and put it in queue.
        # Note: token_callback is called synchronously by LLM.
        # We use loop.call_soon_threadsafe to put into async queue.
        
        # Use the captured main_loop instead of getting it here
        main_loop.call_soon_threadsafe(queue.put_nowait, {"type": "thinking", "content": text})

    # 2. Background task to run the graph
    async def run_graph():
        try:
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 50,
                # Pass callback handler
                "callbacks": [UIStreamingCallbackHandler(token_callback)]
            }
            
            inputs = {
                "messages": [HumanMessage(content=message)],
                "manual_selected_tables": selected_tables
            }
            
            # Stream graph updates
            import time
            step_start_time = time.time()
            
            async for output in graph_app.astream(inputs, config=config):
                print(f"DEBUG: Graph output keys: {list(output.keys())}")
                step_end_time = time.time()
                duration = round((step_end_time - step_start_time) * 1000) # ms
                step_start_time = step_end_time # Reset for next step
                
                for node_name, state_update in output.items():
                    print(f"DEBUG: Processing node output: {node_name}")
                    # Format state update event
                    event_data = {
                        "type": "step",
                        "node": node_name,
                        "status": "completed",
                        "details": "",
                        "duration": duration
                    }
                    
                    # Extract useful details for UI
                    if node_name == "Planner":
                        plan = state_update.get("plan", [])
                        await queue.put({"type": "plan", "content": plan})
                        event_data["details"] = f"已生成 {len(plan)} 步执行计划"

                    elif node_name == "ClarifyIntent":
                        intent_clear = state_update.get("intent_clear", False)
                        event_data["details"] = "意图清晰" if intent_clear else "需要澄清"
                        if not intent_clear:
                             msgs = state_update.get("messages", [])
                             if msgs and isinstance(msgs[-1], AIMessage):
                                 await queue.put({"type": "result", "content": msgs[-1].content})

                    elif node_name == "SelectTables":
                        schema = state_update.get("relevant_schema", "")
                        # Truncate schema for display if too long
                        display_schema = schema[:100] + "..." if len(schema) > 100 else schema
                        event_data["details"] = "已选择相关表:\n" + display_schema
                        
                        # Extract table names from schema string to send back to frontend for checkbox sync
                        # Schema format: "表名: table_name (comment)\n列: ..."
                        import re
                        extracted_tables = []
                        for line in schema.split('\n'):
                            if line.startswith("表名:"):
                                # Extract "table_name" from "表名: table_name" or "表名: table_name (comment)"
                                match = re.match(r"表名:\s*(\w+)", line)
                                if match:
                                    extracted_tables.append(match.group(1))
                        
                        if extracted_tables:
                            await queue.put({"type": "selected_tables", "content": extracted_tables})

                    elif node_name == "GenerateDSL":
                        dsl = state_update.get("dsl", "")
                        event_data["details"] = dsl
                        
                    elif node_name == "DSLtoSQL":
                        sql = state_update.get("sql", "")
                        event_data["details"] = sql
                        
                    elif node_name == "ExecuteSQL":
                        result = state_update.get("results", "")
                        event_data["details"] = "查询成功"
                        # We don't send raw result text if we have analysis/viz coming up
                        # But for now, keep it compatible
                        
                    elif node_name == "DataAnalysis":
                        analysis = state_update.get("analysis", "")
                        event_data["details"] = "数据分析完成"
                        await queue.put({"type": "analysis", "content": analysis})
                        
                    elif node_name == "Visualization":
                        viz = state_update.get("visualization", {})
                        event_data["details"] = "可视化生成完成"
                        if viz:
                            await queue.put({"type": "visualization", "content": viz})
                            
                    elif node_name == "TableQA":
                        msgs = state_update.get("messages", [])
                        if msgs and isinstance(msgs[-1], AIMessage):
                            await queue.put({"type": "result", "content": msgs[-1].content})

                    await queue.put(event_data)
                    
        except Exception as e:
            await queue.put({"type": "error", "content": str(e)})
            import traceback
            traceback.print_exc()
        finally:
            await queue.put(SENTINEL)

    # Start graph execution
    asyncio.create_task(run_graph())
    
    # Consumer loop
    while True:
        data = await queue.get()
        if data is SENTINEL:
            break
        
        # Format as SSE
        # event: <type>
        # data: <json>
        yield f"event: {data['type']}\n"
        yield f"data: {json.dumps(data)}\n\n"

@app.get("/tables")
async def get_tables():
    """
    Get all table schemas from the AppDB for the schema browser.
    Returns detailed JSON structure with columns and comments.
    """
    try:
        app_db = get_app_db()
        # Read from stored cache to avoid slow inspection of 1000 tables
        schema_json = app_db.get_stored_schema_info()
        if not schema_json:
            return {"tables": []}
            
        schema_data = json.loads(schema_json)
        
        # Transform to list for easier frontend consumption
        # { "table_name": { "comment": "...", "columns": [...] } }
        # -> [ { "name": "table_name", "comment": "...", "columns": [...] } ]
        
        tables_list = []
        for name, info in schema_data.items():
            # Handle legacy format where info might be just a list of columns
            if isinstance(info, list):
                tables_list.append({
                    "name": name,
                    "comment": "",
                    "columns": info
                })
            else:
                tables_list.append({
                    "name": name,
                    "comment": info.get("comment", ""),
                    "columns": info.get("columns", [])
                })
        
        # Sort by name
        tables_list.sort(key=lambda x: x["name"])
        
        return {"tables": tables_list}
    except Exception as e:
        return {"error": str(e)}

@app.post("/admin/regenerate")
async def regenerate_data():
    """
    Trigger full database regeneration (1000 tables).
    """
    try:
        query_db = get_query_db()
        app_db = get_app_db()
        
        # Regenerate data
        query_db.regenerate_all_data()
        
        # Sync schema
        schema_info = query_db.inspect_schema()
        app_db.save_schema_info(schema_info)
        
        return {"status": "success", "message": "Database regenerated with 1000 tables across 100 domains."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    return StreamingResponse(
        event_generator(request.message, request.selected_tables, thread_id),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
