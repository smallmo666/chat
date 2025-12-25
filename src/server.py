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

# 忽略警告
warnings.filterwarnings("ignore")

app = FastAPI(title="Text2SQL Agent API")

# 配置跨域资源共享 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 为了演示目的，允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化全局图（只编译一次）
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
    生成器，用于生成来自图状态更新和 LLM 令牌流（通过回调）的 SSE 事件。
    """
    queue = asyncio.Queue()
    
    # 哨兵对象，用于信号流结束
    SENTINEL = object()
    
    # 捕获主事件循环，以便安全地从线程调度回调
    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        # 在异步函数中不应发生，但作为回退
        main_loop = asyncio.new_event_loop()
    
    # 1. LLM 令牌回调
    def token_callback(text: str):
        # 我们只推送*新*的块（如果可能），但 src/utils/callbacks.py 中提供的回调处理程序目前会累积文本。
        # 让我们检查 src/utils/callbacks.py
        # 它调用 update_callback(self.current_text)
        # 为了流式传输效率，最好发送块。
        # 但我们的 UIStreamingCallbackHandler 发送全文？
        # 让我们假设我们想要发送全文更新或块。
        # 为了最小化带宽，块更好，但全文更容易让 UI 同步。
        # 让我们把更新包装在一个字典里放入队列。
        # 注意：token_callback 是由 LLM 同步调用的。
        # 我们使用 loop.call_soon_threadsafe 放入异步队列。
        
        # 使用捕获的 main_loop 而不是在这里获取
        main_loop.call_soon_threadsafe(queue.put_nowait, {"type": "thinking", "content": text})

    # 2. 运行图的后台任务
    async def run_graph():
        try:
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 50,
                # 传递回调处理程序
                "callbacks": [UIStreamingCallbackHandler(token_callback)]
            }
            
            inputs = {
                "messages": [HumanMessage(content=message)],
                "manual_selected_tables": selected_tables
            }
            
            # 流式传输图更新
            import time
            step_start_time = time.time()
            
            async for output in graph_app.astream(inputs, config=config):
                print(f"DEBUG: Graph output keys: {list(output.keys())}")
                step_end_time = time.time()
                duration = round((step_end_time - step_start_time) * 1000) # ms
                step_start_time = step_end_time # 重置为下一步
                
                for node_name, state_update in output.items():
                    print(f"DEBUG: Processing node output: {node_name}")
                    
                    # 忽略 UI 的 Supervisor 事件
                    if node_name == "Supervisor":
                        continue
                        
                    # 格式化状态更新事件
                    event_data = {
                        "type": "step",
                        "node": node_name,
                        "status": "completed",
                        "details": "",
                        "duration": duration
                    }
                    
                    # 提取 UI 的有用详细信息
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
                        # 如果太长，截断 Schema 以便显示
                        display_schema = schema[:100] + "..." if len(schema) > 100 else schema
                        event_data["details"] = "已选择相关表:\n" + display_schema
                        
                        # 从 Schema 字符串中提取表名以发送回前端进行复选框同步
                        # Schema 格式: "表名: table_name (comment)\n列: ..."
                        import re
                        extracted_tables = []
                        for line in schema.split('\n'):
                            if line.startswith("表名:"):
                                # 从 "表名: table_name" 或 "表名: table_name (comment)" 中提取 "table_name"
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
                        # 显式发送结果内容以确保 UI 显示它
                        # 将 Markdown 表格转换为结构化 TableData，以便前端渲染为表格
                        try:
                            # 简单的 Markdown 解析器
                            lines = result.strip().split('\n')
                            if len(lines) >= 3 and '|' in lines[0] and '---' in lines[1]:
                                headers = [h.strip() for h in lines[0].split('|') if h.strip()]
                                table_rows = []
                                for line in lines[2:]:
                                    if '|' in line:
                                        values = [v.strip() for v in line.split('|') if v.strip() or v == '']
                                        # 过滤掉首尾可能的空字符串（由于 Markdown 表格首尾的 |）
                                        # 通常 split('|') 后首尾如果是空串是由于 | 在两端
                                        # 让我们更严谨一点：
                                        row_data = {}
                                        raw_values = [v.strip() for v in line.strip('|').split('|')]
                                        
                                        if len(raw_values) == len(headers):
                                            for i, h in enumerate(headers):
                                                row_data[h] = raw_values[i]
                                            table_rows.append(row_data)
                                
                                # 发送结构化表格数据
                                await queue.put({
                                    "type": "visualization", 
                                    "content": {
                                        "chart_type": "table",
                                        "table_data": {
                                            "columns": headers,
                                            "data": table_rows
                                        }
                                    }
                                })
                            else:
                                # 无法解析为表格，回退到普通文本
                                msgs = state_update.get("messages", [])
                                if msgs and isinstance(msgs[-1], AIMessage):
                                    await queue.put({"type": "result", "content": msgs[-1].content})
                        except Exception as e:
                            print(f"Failed to parse markdown table: {e}")
                            # 回退
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
                            # 检查是否有消息（例如解释为什么没有图表）
                            msgs = state_update.get("messages", [])
                            if msgs and isinstance(msgs[-1], AIMessage):
                                await queue.put({"type": "result", "content": msgs[-1].content})
                            
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

    # 开始图执行
    asyncio.create_task(run_graph())
    
    # 消费者循环
    while True:
        data = await queue.get()
        if data is SENTINEL:
            break
        
        # 格式化为 SSE
        # event: <type>
        # data: <json>
        yield f"event: {data['type']}\n"
        yield f"data: {json.dumps(data)}\n\n"

@app.get("/tables")
async def get_tables():
    """
    从 AppDB 获取所有表 Schema 用于 Schema 浏览器。
    返回包含列和注释的详细 JSON 结构。
    """
    try:
        app_db = get_app_db()
        # 从存储的缓存中读取以避免缓慢检查 1000 个表
        schema_json = app_db.get_stored_schema_info()
        if not schema_json:
            return {"tables": []}
            
        schema_data = json.loads(schema_json)
        
        # 转换为列表以便前端更容易使用
        # { "table_name": { "comment": "...", "columns": [...] } }
        # -> [ { "name": "table_name", "comment": "...", "columns": [...] } ]
        
        tables_list = []
        for name, info in schema_data.items():
            # 处理信息可能只是列列表的旧格式
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
        
        # 按名称排序
        tables_list.sort(key=lambda x: x["name"])
        
        return {"tables": tables_list}
    except Exception as e:
        return {"error": str(e)}

@app.post("/admin/regenerate")
async def regenerate_data():
    """
    触发全量数据库重新生成（1000 个表）。
    """
    try:
        query_db = get_query_db()
        app_db = get_app_db()
        
        # 重新生成数据
        query_db.regenerate_all_data()
        
        # 同步 Schema
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
