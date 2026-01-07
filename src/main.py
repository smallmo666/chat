import sys
import uuid
import warnings
import asyncio
from typing import List, Dict, Any, Optional

# Suppress warnings
warnings.filterwarnings("ignore")

from langchain_core.messages import HumanMessage, AIMessage
from rich.console import Console, Group
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich import box
from src.workflow.graph import create_graph
from src.core.database import get_query_db, get_app_db
from src.utils.callbacks import UIStreamingCallbackHandler
from src.core.logging import setup_logging, console

# console = Console() # Removed local instantiation

def create_ui_layout(plan_steps: List[Dict[str, str]], thinking_text: str = "") -> Group:
    """Create the UI layout with Plan Table and Thinking Panel."""
    
    # Plan Table
    table = Table(box=box.ROUNDED, expand=True)
    table.add_column("步骤", style="cyan")
    table.add_column("状态", style="magenta")
    table.add_column("详情", style="green")

    for step in plan_steps:
        status_icon = ""
        if step["status"] == "pending":
            status_icon = "⏳ 等待中"
        elif step["status"] == "running":
            status_icon = "🔄 执行中..."
        elif step["status"] == "completed":
            status_icon = "✅ 已完成"
        elif step["status"] == "skipped":
            status_icon = "⏭️ 已跳过"
            
        table.add_row(step["name"], status_icon, step.get("detail", ""))
    
    # Thinking Panel (only show if there is content)
    panels = [table]
    if thinking_text:
        thinking_panel = Panel(
            Text(thinking_text, style="dim italic"),
            title="🧠 思考过程",
            border_style="blue",
            expand=True
        )
        panels.append(thinking_panel)
        
    return Group(*panels)

async def main():
    setup_logging()
    console.print(Panel("[bold green]正在初始化 Text2SQL 智能体 (Swarm Edition)...[/bold green]", expand=False))
    
    # Initialization
    try:
        with console.status("[bold green]正在连接数据库...[/bold green]"):
            # 只做连接检查，不强制全量 Schema 同步，避免启动过慢
            query_db = get_query_db()
            app_db = get_app_db()
            # 简单的连通性测试
            await query_db.run_query_async("SELECT 1")
            
            # (Optional) Save basic schema info if needed, but skip full inspection for speed
            # schema_info = query_db.inspect_schema()
            # app_db.save_schema_info(schema_info)
            
        console.print("[bold green]✅ 系统初始化完成！[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ 初始化失败: {e}[/bold red]")
        sys.exit(1)
        
    app = create_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    
    console.print(f"[dim]会话 ID: {thread_id}[/dim]")
    console.print(Panel("[bold yellow]欢迎使用 Text2SQL 助手！[/bold yellow]\n请输入您的查询，输入 'exit' 退出。", expand=False))
    
    # Global state for thinking text
    thinking_state = {"text": ""}
    
    def update_thinking(text: str):
        thinking_state["text"] = text

    config["callbacks"] = [UIStreamingCallbackHandler(update_thinking)]

    while True:
        try:
            # Note: console.input is blocking
            user_input = await asyncio.to_thread(console.input, "\n[bold cyan]用户 > [/bold cyan]")
            user_input = user_input.strip()
            
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                console.print("[bold yellow]再见！[/bold yellow]")
                break
            
            # Dynamic Plan Template - Updated for Swarm Architecture
            # We start with high-level phases, detailed steps will be filled by 'Planner' node
            plan_steps = [
                {"id": "CacheCheck", "name": "0. 缓存检查", "status": "pending", "detail": ""},
                {"id": "DataDetective", "name": "1. 侦探分析", "status": "pending", "detail": ""},
                {"id": "Planner", "name": "2. 任务规划", "status": "pending", "detail": ""},
                {"id": "Supervisor", "name": "3. 任务执行", "status": "pending", "detail": "等待调度..."},
            ]
            
            thinking_state["text"] = ""
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            # Start Live Display
            with Live(create_ui_layout(plan_steps, thinking_state["text"]), refresh_per_second=10, console=console) as live:
                
                async def refresh_ui_loop():
                    while True:
                        live.update(create_ui_layout(plan_steps, thinking_state["text"]))
                        await asyncio.sleep(0.1)

                refresh_task = asyncio.create_task(refresh_ui_loop())
                
                def update_step(step_id, status, detail=""):
                    found = False
                    for step in plan_steps:
                        if step["id"] == step_id:
                            step["status"] = status
                            if detail:
                                step["detail"] = detail
                            found = True
                    
                    # If step not found (e.g. dynamically added by Planner), add it
                    if not found and step_id not in ["Supervisor", "FINISH"]:
                         plan_steps.append({"id": step_id, "name": step_id, "status": status, "detail": detail})
                         
                    live.update(create_ui_layout(plan_steps, thinking_state["text"]))

                try:
                    async for output in app.astream(inputs, config=config):
                        for node_name, state_update in output.items():
                            
                            # Update Status based on Node
                            if node_name == "CacheCheck":
                                update_step("CacheCheck", "completed", "检查完毕")
                                
                            elif node_name == "DataDetective":
                                update_step("CacheCheck", "completed") # Ensure prev
                                update_step("DataDetective", "completed", "分析完成")
                                
                            elif node_name == "Planner":
                                update_step("DataDetective", "completed")
                                plan = state_update.get("plan", [])
                                update_step("Planner", "completed", f"生成 {len(plan)} 步计划")
                                # Optional: Dynamically expand plan_steps based on plan
                                
                            elif node_name == "Supervisor":
                                next_node = state_update.get("next")
                                update_step("Supervisor", "running", f"调度 -> {next_node}")

                            elif node_name == "ExecuteSQL":
                                result = state_update.get("results", "执行完成")
                                update_step("ExecuteSQL", "completed", "查询成功")
                                
                                msgs = state_update.get("messages", [])
                                if msgs and isinstance(msgs[-1], AIMessage):
                                    live.stop()
                                    console.print(f"\n[bold green]查询结果:[/bold green]")
                                    console.print(msgs[-1].content)
                                    live.start()
                            
                            elif node_name in ["ClarifyIntent", "GenerateDSL", "DSLtoSQL", "CorrectSQL", "Visualization", "PythonAnalysis", "InsightMiner", "UIArtist"]:
                                # Generic handler for worker nodes
                                update_step(node_name, "completed", "执行完成")
                                
                                # Show result if available
                                msgs = state_update.get("messages", [])
                                if msgs and isinstance(msgs[-1], AIMessage):
                                     content = msgs[-1].content
                                     if len(content) < 200: # Only show short messages
                                         update_step(node_name, "completed", content)

                            # Reset thinking text
                            thinking_state["text"] = ""
                            
                finally:
                    refresh_task.cancel()
                    try:
                        await refresh_task
                    except asyncio.CancelledError:
                        pass

            console.print("-" * 50, style="dim")
            
        except KeyboardInterrupt:
            console.print("\n[bold yellow]再见！[/bold yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]执行错误: {e}[/bold red]")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
