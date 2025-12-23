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

from src.graph import create_graph
from src.utils.db import get_query_db, get_app_db

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
    # 增加递归限制，避免死循环错误
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    
    console.print(f"[dim]会话 ID: {thread_id}[/dim]")
    console.print(Panel("[bold yellow]欢迎使用 Text2SQL 助手！[/bold yellow]\n请输入您的查询，输入 'exit' 退出。", expand=False))
    
    while True:
        try:
            # Note: console.input is blocking, but that's fine for CLI loop
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
            
            current_thinking = ""
            current_node = None
            
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            # Use Live display
            with Live(create_ui_layout(plan_steps, current_thinking), refresh_per_second=10, console=console) as live:
                
                def update_step(step_id, status, detail=""):
                    for step in plan_steps:
                        if step["id"] == step_id:
                            step["status"] = status
                            if detail:
                                step["detail"] = detail
                
                # Use astream_events to capture token streaming
                async for event in app.astream_events(inputs, config=config, version="v1"):
                    kind = event["event"]
                    name = event["name"]
                    data = event["data"]
                    
                    # 1. Handle Chain/Node Start/End to update plan status
                    if kind == "on_chain_start":
                        if name in ["ClarifyIntent", "GenerateDSL", "DSLtoSQL", "ExecuteSQL"]:
                            current_node = name
                            update_step(name, "running")
                            # Clear thinking buffer for new step
                            current_thinking = ""
                            live.update(create_ui_layout(plan_steps, current_thinking))
                            
                    elif kind == "on_chain_end":
                        # We handle completion logic based on outputs below, or generic completion here
                        if name == "ClarifyIntent":
                            # Check output to see if clarification needed
                            output = data.get("output", {})
                            if output and isinstance(output, dict):
                                if output.get("intent_clear") is False:
                                    update_step(name, "completed", "需要澄清")
                                else:
                                    update_step(name, "completed", "意图清晰")
                        
                        elif name == "GenerateDSL":
                            output = data.get("output", {})
                            if output and isinstance(output, dict):
                                dsl = output.get("dsl", "")
                                display_dsl = (dsl[:30] + '...') if len(dsl) > 30 else dsl
                                update_step(name, "completed", display_dsl)
                        
                        elif name == "DSLtoSQL":
                            output = data.get("output", {})
                            if output and isinstance(output, dict):
                                sql = output.get("sql", "")
                                update_step(name, "completed", sql)

                        elif name == "ExecuteSQL":
                            update_step(name, "completed", "查询成功")

                    # 2. Handle Streaming Tokens (Thinking Process)
                    elif kind == "on_chat_model_stream":
                        chunk = data.get("chunk")
                        if chunk:
                            content = chunk.content
                            if content:
                                current_thinking += content
                                live.update(create_ui_layout(plan_steps, current_thinking))
                    
                    # 3. Handle Final Agent Responses (Clarification or Results)
                    # We usually detect this via on_chain_end of the specific node, but extracting the full message
                    # is easier if we look at the node output.
                    
                    # However, astream_events yields granular events. 
                    # To print the final distinct message (like the table result or question), 
                    # we can wait for the loop to finish, OR check `on_chain_end` for specific nodes.
                    
                    if kind == "on_chain_end" and name in ["ClarifyIntent", "ExecuteSQL"]:
                        output = data.get("output", {})
                        if output and isinstance(output, dict) and "messages" in output:
                            last_msg = output["messages"][-1]
                            if isinstance(last_msg, AIMessage):
                                # If it's a clarification question
                                if name == "ClarifyIntent" and output.get("intent_clear") is False:
                                    live.stop()
                                    console.print(Panel(f"[bold yellow]Agent:[/bold yellow] {last_msg.content}", title="需确认"))
                                    live.start()
                                
                                # If it's a result
                                if name == "ExecuteSQL":
                                    live.stop()
                                    console.print(f"\n[bold green]查询结果:[/bold green]")
                                    console.print(last_msg.content)
                                    live.start()

            console.print("-" * 50, style="dim")
            
        except KeyboardInterrupt:
            console.print("\n[bold yellow]再见！[/bold yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]执行错误: {e}[/bold red]")

if __name__ == "__main__":
    asyncio.run(main())
