from src.state.state import AgentState
from src.utils.schema_search import get_schema_searcher
import json

def select_tables_node(state: AgentState, config: dict) -> dict:
    """
    表选择节点。
    根据用户的查询，从大规模数据库中检索出最相关的表结构。
    如果存在用户手动选择的表，优先使用。
    """
    manual_tables = state.get("manual_selected_tables", [])
    searcher = get_schema_searcher()

    if manual_tables and len(manual_tables) > 0:
        # 用户显式选择了表。
        # 我们需要获取这些特定表的 Schema。
        
        # 限制手动表的数量以避免 Context 爆炸
        if len(manual_tables) > 20:
            manual_tables = manual_tables[:20]
            print(f"Warning: Too many manual tables selected. Truncating to top 20.")
            
        # 暂时从缓存手动构建 Schema 字符串以保持简单
        full_schema = searcher._get_schema()
        relevant_schema_info = []
        for table in manual_tables:
            if table in full_schema:
                # 处理旧版格式的 dict 和 list
                info = full_schema[table]
                columns = info if isinstance(info, list) else info.get("columns", [])
                
                col_strings = [f"{col['name']} ({col['type']})" + (f" - {col.get('comment')}" if col.get('comment') else "") for col in columns]
                table_comment = info.get("comment", "") if isinstance(info, dict) else ""
                
                header = f"表名: {table}"
                if table_comment:
                    header += f" ({table_comment})"
                
                relevant_schema_info.append(f"{header}\n列: {', '.join(col_strings)}")
        
        if not relevant_schema_info:
             # 如果未找到手动表（罕见），则回退
             schema_info = "User selected tables not found in schema."
        else:
             schema_info = "\n\n".join(relevant_schema_info)
             
        return {"relevant_schema": schema_info}

    messages = state["messages"]
    # 获取最新的用户查询
    last_human_msg = ""
    for msg in reversed(messages):
        if msg.type == "human":
            last_human_msg = msg.content
            break
            
    if not last_human_msg:
        return {"relevant_schema": "No user query found."}

    # 检索相关表 Schema
    schema_info = searcher.search_relevant_tables(last_human_msg)
    
    # 打印日志方便调试
    # print(f"Selected Schema: {schema_info[:100]}...")
    
    # 我们不直接返回 messages，而是更新 state 中的 schema 信息
    # 注意：StateGraph 的 schema 需要支持这个字段，或者我们将其作为临时变量传递
    # 这里我们假设 generate_dsl_node 会从 state 中读取这个信息，或者我们通过某种方式传递
    # 由于 LangGraph state 是 dict，我们可以直接写入
    return {"relevant_schema": schema_info}
