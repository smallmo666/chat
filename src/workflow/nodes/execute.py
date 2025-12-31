import json
import re
from langchain_core.messages import AIMessage
from src.workflow.state import AgentState
from src.core.database import get_query_db
from src.core.sql_security import is_safe_sql
from src.workflow.utils.memory_sync import sync_memory
import asyncio

# 定义敏感字段列表 (可配置)
SENSITIVE_FIELDS = {
    "salary": "masked",
    "password": "masked",
    "ssn": "masked",
    "phone": "partial_masked",
    "email": "partial_masked",
    "credit_card": "masked"
}

def apply_privacy_filter(data_list: list) -> list:
    """
    对数据列表应用隐私过滤。
    """
    if not data_list:
        return []
    
    # 浅拷贝第一条数据来检查字段名
    first_row = data_list[0]
    sensitive_cols = []
    
    for col in first_row.keys():
        col_lower = col.lower()
        for sens_key, strategy in SENSITIVE_FIELDS.items():
            if sens_key in col_lower:
                sensitive_cols.append((col, strategy))
                break
    
    if not sensitive_cols:
        return data_list
        
    print(f"DEBUG: PrivacyFilter - Detected sensitive columns: {sensitive_cols}")
    
    filtered_data = []
    for row in data_list:
        new_row = row.copy()
        for col, strategy in sensitive_cols:
            val = str(new_row.get(col, ""))
            if strategy == "masked":
                new_row[col] = "***"
            elif strategy == "partial_masked":
                if len(val) > 4:
                    new_row[col] = val[:2] + "****" + val[-2:]
                else:
                    new_row[col] = "***"
        filtered_data.append(new_row)
        
    return filtered_data

async def execute_sql_node(state: AgentState, config: dict) -> dict:
    """
    SQL 执行节点。
    在 QueryDatabase 中执行生成的 SQL 并返回结果。
    同时将成功的查询交互同步到长期记忆中。
    **增强**: 集成隐私过滤 (Privacy Layer)。
    """
    sql = state.get("sql")
    if not sql:
        return {
            "error": "状态中未找到可执行的 SQL。",
            "results": "错误: 未生成 SQL。"
        }

    # 安全检查
    if not is_safe_sql(sql):
        error_msg = f"安全警告: SQL 包含禁止的关键字或复杂的嵌套语句。执行被阻止。\nSQL: {sql}"
        return {
            "error": error_msg,
            "results": "执行被阻止: 违反安全策略"
        }

    # 执行查询
    db = get_query_db()
    
    try:
        # 异步执行
        db_result = await db.run_query_async(sql)
        
        if db_result.get("error"):
             raise Exception(db_result["error"])
        
        json_result_str = db_result.get("json", "[]")
        json_result = json.loads(json_result_str)

        # --- Privacy Filter ---
        if isinstance(json_result, list) and len(json_result) > 0:
            json_result = apply_privacy_filter(json_result)
            # 更新 json_result_str
            json_result_str = json.dumps(json_result, ensure_ascii=False)
        # ----------------------

        # 准备数据以同步记忆
        user_id = config.get("configurable", {}).get("thread_id", "default_user")
        project_id = config.get("configurable", {}).get("project_id")
        dsl = state.get("dsl", "")
        
        # 确定用户查询
        rewritten_query = state.get("rewritten_query")
        messages = state.get("messages", [])
        user_query = "未知查询"
        
        if rewritten_query:
            user_query = rewritten_query
        else:
            for msg in reversed(messages):
                if msg.type == "human":
                    user_query = msg.content
                    break
        
        # 同步记忆
        await sync_memory(user_id, project_id, user_query, dsl, sql, json_result_str)
        
        return {
            "results": json_result_str,
            "messages": [AIMessage(content=f"查询执行成功，找到 {len(json_result)} 条记录。")],
            "error": None,
            "retry_count": 0
        }
        
    except Exception as e:
        error_msg = str(e)
        if "read only" in error_msg.lower():
             error_msg = f"数据库错误: 数据库处于只读模式。请检查您的查询或数据库配置。 ({error_msg})"

        return {
            "error": error_msg,
            "results": f"SQL 执行失败: {error_msg}"
        }
