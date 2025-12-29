import asyncio
import json
import uuid
import warnings
from typing import AsyncGenerator, Optional, List

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel
from sqlmodel import Session, select

from src.graph import create_graph
from src.utils.db import get_query_db, get_app_db, QueryDatabase, AppDatabase
from src.models import DataSource, Project, AuditLog
from src.utils.callbacks import UIStreamingCallbackHandler

# 忽略警告
warnings.filterwarnings("ignore")

app = FastAPI(title="Text2SQL Agent API")

# 配置跨域资源共享 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 为了演示目的，允许所有来源
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化全局图（只编译一次）
graph_app = None

# --- Pydantic Models for API ---
class DataSourceCreate(BaseModel):
    name: str
    type: str = "postgresql"
    host: str
    port: int
    user: str
    password: str
    dbname: str

class DataSourceRead(BaseModel):
    id: int
    name: str
    type: str
    host: str
    port: int
    user: str
    dbname: str

class ProjectCreate(BaseModel):
    name: str
    data_source_id: int
    scope_config: Optional[dict] = {}

class ProjectRead(BaseModel):
    id: int
    name: str
    data_source_id: int
    scope_config: dict

class ChatRequest(BaseModel):
    message: str
    project_id: Optional[int] = None
    thread_id: Optional[str] = None
    selected_tables: Optional[list[str]] = None

@app.on_event("startup")
async def startup_event():
    global graph_app
    print("Initializing Text2SQL Agent...")
    # Initialize DB (ensure tables created)
    try:
        get_app_db()
    except Exception as e:
        print(f"DB Init error: {e}")

    try:
        graph_app = create_graph()
        print("Graph initialized.")
    except Exception as e:
        print(f"Graph initialization failed: {e}")
        import traceback
        traceback.print_exc()

# --- Data Source APIs ---
@app.post("/api/datasources", response_model=DataSourceRead)
def create_datasource(ds: DataSourceCreate, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        db_ds = DataSource.from_orm(ds)
        session.add(db_ds)
        session.commit()
        session.refresh(db_ds)
        return db_ds

@app.put("/api/datasources/{id}", response_model=DataSourceRead)
def update_datasource(id: int, ds: DataSourceCreate, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        db_ds = session.get(DataSource, id)
        if not db_ds:
            raise HTTPException(status_code=404, detail="DataSource not found")
        
        # Update fields
        db_ds.name = ds.name
        db_ds.type = ds.type
        db_ds.host = ds.host
        db_ds.port = ds.port
        db_ds.user = ds.user
        db_ds.password = ds.password
        db_ds.dbname = ds.dbname
        
        session.add(db_ds)
        session.commit()
        session.refresh(db_ds)
        return db_ds

@app.post("/api/datasources/test")
def test_datasource_connection(ds: DataSourceCreate):
    from sqlalchemy import text
    try:
        # Temporarily create a DataSource object (not saved to DB)
        temp_ds = DataSource(
            name="test",
            type=ds.type,
            host=ds.host,
            port=ds.port,
            user=ds.user,
            password=ds.password,
            dbname=ds.dbname
        )
        # Try to initialize QueryDatabase which establishes connection
        db = QueryDatabase(temp_ds)
        # Verify connection with a simple query
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "message": "Connection successful"}
    except Exception as e:
        print(f"Test connection failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/datasources", response_model=List[DataSourceRead])
def get_datasources(app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        datasources = session.exec(select(DataSource)).all()
        return datasources

@app.delete("/api/datasources/{id}")
def delete_datasource(id: int, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        ds = session.get(DataSource, id)
        if not ds:
            raise HTTPException(status_code=404, detail="DataSource not found")
        session.delete(ds)
        session.commit()
        return {"ok": True}

# --- Project APIs ---
@app.post("/api/projects", response_model=ProjectRead)
def create_project(proj: ProjectCreate, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        db_proj = Project.from_orm(proj)
        session.add(db_proj)
        session.commit()
        session.refresh(db_proj)
        return db_proj

@app.get("/api/projects", response_model=List[ProjectRead])
def get_projects(app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        projects = session.exec(select(Project)).all()
        return projects

@app.get("/api/projects/{id}", response_model=ProjectRead)
def get_project(id: int, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        proj = session.get(Project, id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        return proj

# --- Audit APIs ---
@app.get("/api/audit/logs")
def get_audit_logs(project_id: Optional[int] = None, session_id: Optional[str] = None, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        query = select(AuditLog)
        if project_id:
            query = query.where(AuditLog.project_id == project_id)
        if session_id:
            query = query.where(AuditLog.session_id == session_id)
        logs = session.exec(query.order_by(AuditLog.created_at.desc()).limit(100)).all()
        return logs

# --- Chat & Schema APIs (Updated) ---

async def event_generator(message: str, selected_tables: Optional[list[str]], thread_id: str, project_id: Optional[int]) -> AsyncGenerator[str, None]:
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
            # Inject project_id into config if needed, or rely on global context?
            # Ideally, graph nodes should access DB via dependency injection or context var.
            # But LangGraph nodes run in threads/processes.
            # We can pass project_id in configurable.
            
            config = {
                "configurable": {"thread_id": thread_id, "project_id": project_id},
                "recursion_limit": 50,
                "callbacks": [UIStreamingCallbackHandler(token_callback)]
            }
            
            inputs = {
                "messages": [HumanMessage(content=message)],
                "manual_selected_tables": selected_tables
            }
            
            import time
            step_start_time = time.time()
            
            # TODO: Audit Log Start
            
            async for output in graph_app.astream(inputs, config=config):
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
                        
                    elif node_name == "DSLtoSQL":
                        sql = state_update.get("sql", "")
                        event_data["details"] = sql
                        
                    elif node_name == "ExecuteSQL":
                        results_json_str = state_update.get("results", "[]")
                        event_data["details"] = "查询成功"
                        try:
                            json_data = json.loads(results_json_str)
                            if isinstance(json_data, list) and len(json_data) > 0:
                                await queue.put({"type": "data_export", "content": json_data})
                        except Exception as e:
                            print(f"Failed to parse results JSON for export: {e}")

                        msgs = state_update.get("messages", [])
                        if msgs and isinstance(msgs[-1], AIMessage):
                            await queue.put({"type": "result", "content": msgs[-1].content})
                        
                    elif node_name == "DataAnalysis":
                        analysis = state_update.get("analysis", "")
                        event_data["details"] = "数据分析完成"
                        await queue.put({"type": "analysis", "content": analysis})
                        
                    elif node_name == "Visualization":
                        viz = state_update.get("visualization", {})
                        event_data["details"] = "可视化生成完成"
                        if viz:
                            await queue.put({"type": "visualization", "content": viz})
                        else:
                            msgs = state_update.get("messages", [])
                            if msgs and isinstance(msgs[-1], AIMessage):
                                await queue.put({"type": "result", "content": msgs[-1].content})
                            
                    elif node_name == "TableQA":
                        msgs = state_update.get("messages", [])
                        if msgs and isinstance(msgs[-1], AIMessage):
                            await queue.put({"type": "result", "content": msgs[-1].content})

                    await queue.put(event_data)
            
            # TODO: Audit Log End (Success)
                    
        except Exception as e:
            # TODO: Audit Log End (Error)
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

@app.get("/tables")
def get_tables(project_id: Optional[int] = Query(None), app_db: AppDatabase = Depends(get_app_db)):
    """
    Get tables for schema browser.
    If project_id is provided, use its data source.
    Otherwise fallback to legacy/default.
    """
    try:
        if project_id:
            # Load project specific schema
            # We need to instantiate QueryDatabase with project context
            # This logic should ideally be inside QueryDatabase.inspect_schema or similar
            # But QueryDatabase is usually per-request.
            
            # For simplicity, we can reuse get_query_db logic here manually or refactor dependency
            query_db = get_query_db(project_id)
            
            # Get Project Scope
            with app_db.get_session() as session:
                project = session.get(Project, project_id)
                scope = project.scope_config if project else None
            
            schema_json = query_db.inspect_schema(scope)
        else:
            # Legacy: read from cache or default
            # For now, let's just inspect default DB live (it's fast enough usually)
            # or use the old logic if we kept it.
            # But since we refactored DB, let's just inspect live default.
            query_db = get_query_db() # Default env
            schema_json = query_db.inspect_schema()

        if not schema_json:
            return {"tables": []}
            
        schema_data = json.loads(schema_json)
        
        tables_list = []
        for name, info in schema_data.items():
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
        
        tables_list.sort(key=lambda x: x["name"])
        return {"tables": tables_list}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    return StreamingResponse(
        event_generator(request.message, request.selected_tables, thread_id, request.project_id),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
