from langchain_core.messages import AIMessage
from src.state.state import AgentState
from src.utils.db import get_query_db
from src.utils.memory import get_memory

def execute_sql_node(state: AgentState, config: dict) -> dict:
    """
    执行 SQL 节点。
    获取生成的 SQL，在 QueryDatabase (querydb) 中执行，并返回结果。
    同时将成功的查询交互保存到长期记忆中。
    """
    sql = state.get("sql")
    # 使用 QueryDatabase 进行查询执行
    db = get_query_db()
    
    result_str = db.run_query(sql)
    
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
            print(f"已保存到长期记忆: {memory_text}")
        else:
            print(f"未能保存到长期记忆 (未初始化或错误)")
    except Exception as e:
        print(f"保存记忆失败: {e}")
    
    # 我们返回结果，并将其作为一条消息添加到历史记录中
    return {
        "results": result_str,
        "messages": [AIMessage(content=f"查询结果:\n{result_str}")]
    }
