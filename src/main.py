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

console = Console()

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
    console.print(Panel("[bold green]正在初始化 Text2SQL 智能体...[/bold green]", expand=False))
    
    # Initialization
    try:
        with console.status("[bold green]正在连接数据库并同步 Schema...[/bold green]"):
            query_db = get_query_db()
            app_db = get_app_db()
            query_db.ensure_demo_data()
            schema_info = query_db.inspect_schema()
            app_db.save_schema_info(schema_info)
        console.print("[bold green]✅ 系统初始化完成！[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ 初始化失败: {e}[/bold red]")
        sys.exit(1)
        
    app = create_graph()
    thread_id = str(uuid.uuid4())
    # 增加递归限制
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    
    console.print(f"[dim]会话 ID: {thread_id}[/dim]")
    console.print(Panel("[bold yellow]欢迎使用 Text2SQL 助手！[/bold yellow]\n请输入您的查询，输入 'exit' 退出。", expand=False))
    
    # Global state for thinking text (shared with callback)
    thinking_state = {"text": ""}
    
    def update_thinking(text: str):
        thinking_state["text"] = text

    # Add callback to config
    # Note: app.astream accepts config, and callbacks in config should propagate to models
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
            
            # Initial Plan Template
            plan_steps = [
                {"id": "ClarifyIntent", "name": "1. 意图分析", "status": "pending", "detail": ""},
                {"id": "GenerateDSL", "name": "2. 生成 DSL", "status": "pending", "detail": ""},
                {"id": "DSLtoSQL", "name": "3. 生成 SQL", "status": "pending", "detail": ""},
                {"id": "ExecuteSQL", "name": "4. 执行查询", "status": "pending", "detail": ""},
            ]
            
            thinking_state["text"] = ""
            
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            # Start Live Display
            # Use refresh_per_second=10 to auto-update based on current state
            with Live(create_ui_layout(plan_steps, thinking_state["text"]), refresh_per_second=10, console=console) as live:
                
                # Background task to refresh UI continuously during stream
                async def refresh_ui_loop():
                    while True:
                        live.update(create_ui_layout(plan_steps, thinking_state["text"]))
                        await asyncio.sleep(0.1)

                refresh_task = asyncio.create_task(refresh_ui_loop())
                
                def update_step(step_id, status, detail=""):
                    for step in plan_steps:
                        if step["id"] == step_id:
                            step["status"] = status
                            if detail:
                                step["detail"] = detail
                    # Immediate update
                    live.update(create_ui_layout(plan_steps, thinking_state["text"]))

                try:
                    # Use app.astream (standard) instead of astream_events
                    async for output in app.astream(inputs, config=config):
                        # output is a dict of {NodeName: StateUpdate}
                        for node_name, state_update in output.items():
                            
                            # Update Plan Status based on Node completion
                            if node_name == "ClarifyIntent":
                                intent_clear = state_update.get("intent_clear", False)
                                if intent_clear:
                                    update_step("ClarifyIntent", "completed", "意图清晰")
                                else:
                                    update_step("ClarifyIntent", "completed", "需要澄清")
                                    # Handle clarification message
                                    msgs = state_update.get("messages", [])
                                    if msgs and isinstance(msgs[-1], AIMessage):
                                        live.stop()
                                        console.print(Panel(f"[bold yellow]Agent:[/bold yellow] {msgs[-1].content}", title="需确认"))
                                        live.start()

                            elif node_name == "GenerateDSL":
                                update_step("ClarifyIntent", "completed", "意图清晰") # Ensure previous
                                dsl = state_update.get("dsl", "")
                                display_dsl = (dsl[:30] + '...') if len(dsl) > 30 else dsl
                                update_step("GenerateDSL", "completed", display_dsl)

                            elif node_name == "DSLtoSQL":
                                update_step("GenerateDSL", "completed")
                                sql = state_update.get("sql", "")
                                update_step("DSLtoSQL", "completed", sql)

                            elif node_name == "ExecuteSQL":
                                update_step("DSLtoSQL", "completed")
                                result = state_update.get("results", "执行完成")
                                update_step("ExecuteSQL", "completed", "查询成功")
                                
                                msgs = state_update.get("messages", [])
                                if msgs and isinstance(msgs[-1], AIMessage):
                                    live.stop()
                                    console.print(f"\n[bold green]查询结果:[/bold green]")
                                    console.print(msgs[-1].content)
                                    live.start()
                            
                            # Reset thinking text for next step (optional, or keep accumulating)
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
