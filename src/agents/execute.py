import json
import re
from langchain_core.messages import AIMessage
from src.state.state import AgentState
from src.utils.db import get_query_db
from src.utils.memory import get_memory
from src.utils.security import is_safe_sql

def execute_sql_node(state: AgentState, config: dict) -> dict:
    """
    执行 SQL 节点。
    获取生成的 SQL，在 QueryDatabase (querydb) 中执行，并返回结果。
    同时将成功的查询交互保存到长期记忆中。
    """
    sql = state.get("sql")
    if not sql:
        return {
            "error": "No SQL found in state to execute.",
            "results": "Error: No SQL generated."
        }

    # Security Check
    if not is_safe_sql(sql):
        error_msg = f"Security Alert: SQL contains forbidden keywords (DROP, DELETE, UPDATE, etc.). Execution blocked.\nSQL: {sql}"
        return {
            "error": error_msg,
            "results": "Execution Blocked: Security Violation"
        }

    # 使用 QueryDatabase 进行查询执行
    db = get_query_db()
    
    try:
        # result_str 以前是字符串，现在是字典
        db_result = db.run_query(sql)
        
        # 检查数据库执行层面的错误 (虽然 db.run_query 内部 catch 了，但会返回 error 字段)
        if db_result.get("error"):
             raise Exception(db_result["error"])
        
        markdown_result = db_result.get("markdown", "")
        json_result = db_result.get("json", "[]")

        # 保存到长期记忆
        # 获取用户 ID
        user_id = config.get("configurable", {}).get("thread_id", "default_user")
        
        # 构建记忆内容：用户的查询意图 + 生成的 SQL
        # 我们从 messages 中找到最近的一条 HumanMessage 作为用户的查询
        # 注意：在多轮对话中，可能需要更复杂的逻辑来确定原始查询，这里简化处理
        messages = state.get("messages", [])
        user_query = "未知查询"
        for msg in reversed(messages):
            if msg.type == "human":
                user_query = msg.content
                break
                
        memory_text = f"用户查询: {user_query} -> 生成 SQL: {sql}"
        
        try:
            memory_client = get_memory()
            if memory_client.add(user_id=user_id, text=memory_text):
                # print(f"已保存到长期记忆: {memory_text}")
                pass
            else:
                # print(f"未能保存到长期记忆 (未初始化或错误)")
                pass
        except Exception as e:
            # print(f"保存记忆失败: {e}")
            pass
        
        # 我们返回结果，并将其作为一条消息添加到历史记录中
        # 注意：为了防止 Context Window 溢出，如果结果过长，我们在历史记录中只保存摘要。
        # 完整结果仍然通过 'results' 键传递给后续节点（如 DataAnalysis）。
        # 修改：我们将 'results' 字段改为存储 JSON 数据，以便后续 Agent 更好处理。
        
        display_result = markdown_result
        # 增加截断长度以支持更多数据的表格展示，避免破坏表格结构
        # 一般 LLM 上下文足够大，我们可以保留更多
        if len(markdown_result) > 5000:
            display_result = markdown_result[:5000] + "\n\n... (结果过长已截断，完整结果用于后续分析)"
            
        return {
            "results": json_result, # Store JSON string for agents
            # 移除 Markdown 表格展示，仅返回摘要提示，强制前端依赖 Visualization 节点渲染表格组件
            "messages": [AIMessage(content=f"查询执行成功，共找到 {len(json.loads(json_result))} 条记录。")],
            "error": None, # Clear error on success
            "retry_count": 0 # Reset retry count on success
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # 针对只读副本错误的特殊处理
        # 如果是 "read only" 错误，但 SQL 看起来是安全的 (SELECT)，这通常意味着
        # 数据库连接配置为了只读，但某些操作（如 Pandas 内部临时表）触发了写检查，或者用户真的在写。
        # 但如果是 SELECT，我们应该提示用户检查配置。
        if "read only" in error_msg.lower():
             error_msg = f"Database Error: The database is in read-only mode. Please check your query or database configuration. ({error_msg})"

        return {
            "error": error_msg,
            "results": f"SQL Execution Failed: {error_msg}"
        }
