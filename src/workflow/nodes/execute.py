import json
from langchain_core.messages import AIMessage
from src.workflow.state import AgentState
from src.core.database import get_query_db
from src.core.sql_security import is_safe_sql
from src.workflow.utils.memory_sync import sync_memory
from src.core.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from src.core.config import settings
from src.core.redis_client import get_redis_client
import time

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

async def analyze_empty_result(sql: str, project_id: int = None) -> str:
    """
    分析空结果原因并生成建议。
    """
    try:
        llm = get_llm(node_name="ExecuteSQL_Analyzer", project_id=project_id)
        # Use from_messages to avoid curly brace parsing issues in the SQL variable
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个 SQL 分析专家。"),
            ("human", 
             "SQL Query: {sql}\n\n"
             "执行结果: 空 (0 行)\n\n"
             "请分析可能导致结果为空的原因（例如：WHERE 条件过严、拼写错误、时间范围不匹配等）。\n"
             "并给出一个“放宽条件”的建议 SQL (只给建议，不要写 SQL 代码)。\n"
             "用简短的中文回答，不超过 2 句话。")
        ])
        chain = prompt | llm
        result = await chain.ainvoke({"sql": sql})
        return result.content.strip()
    except Exception as e:
        print(f"Empty result analysis failed: {e}")
        return "建议检查查询条件是否过严。"

async def summarize_results(data: list, project_id: int = None) -> str:
    """
    生成数据摘要。
    """
    try:
        llm = get_llm(node_name="ExecuteSQL_Summarizer", project_id=project_id)
        
        # 数据采样 (只取前 10 行和统计信息)
        sample = data[:10]
        row_count = len(data)
        
        # Use from_messages to safely handle JSON strings in variables
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个数据分析助手。"),
            ("human", 
             "数据统计: 共 {row_count} 行。\n"
             "数据样本 (前10行): {sample}\n\n"
             "请用一句话总结这些数据的关键信息（例如总数、趋势、最大值等）。")
        ])
        
        chain = prompt | llm
        result = await chain.ainvoke({"row_count": row_count, "sample": json.dumps(sample, ensure_ascii=False)})
        return result.content.strip()
    except Exception as e:
        print(f"Result summarization failed: {e}")
        return f"共找到 {len(data)} 条记录。"

async def execute_sql_node(state: AgentState, config: dict) -> dict:
    """
    SQL 执行节点。
    在 QueryDatabase 中执行生成的 SQL 并返回结果。
    同时将成功的查询交互同步到长期记忆中。
    **增强**: 集成隐私过滤 (Privacy Layer)。
    """
    print("DEBUG: Entering execute_sql_node")
    if state.get("interrupt_pending"):
        return {"results": "中断：已暂停执行", "error": None}
    sql = state.get("sql")
    print(f"DEBUG: execute_sql_node - SQL: {sql}")

    if not sql:
        return {
            "error": "状态中未找到可执行的 SQL。",
            "results": "错误: 未生成 SQL。"
        }

    # 内存保护: 强制添加 LIMIT
    # 如果用户明确要求全量 (e.g. "导出所有数据"), 可以通过 LLM 或 DSL 标记跳过此步骤
    # 这里简单地检查 SQL 是否已有 LIMIT，如果没有且不是聚合查询 (COUNT/SUM)，则添加 LIMIT 1000
    if "limit" not in sql.lower() and "count(" not in sql.lower():
        # 简单追加。注意：如果 SQL 结尾有分号，需要处理
        sql = sql.strip().rstrip(';') + " LIMIT 1000"
        print(f"DEBUG: Auto-added LIMIT clause: {sql}")

    # 安全检查
    if not is_safe_sql(sql):
        error_msg = f"安全警告: SQL 包含禁止的关键字或复杂的嵌套语句。执行被阻止。\nSQL: {sql}"
        return {
            "error": error_msg,
            "results": "执行被阻止: 违反安全策略"
        }

    # 获取 Project ID
    project_id = config.get("configurable", {}).get("project_id")
    
    # 执行查询
    try:
        db = get_query_db(project_id)
    except ValueError as e:
        return {
            "error": f"配置错误: {str(e)}",
            "results": f"系统配置错误: 无法连接到查询数据库。原因: {str(e)}",
            "retry_count": 999, # 防止 CorrectSQL 进行无效重试
            "plan_retry_count": 999, # 防止 Supervisor 进行无效重试
            "messages": [AIMessage(content=f"❌ 系统配置错误: 无法连接到查询数据库。\n原因: {str(e)}")]
        }
    
    try:
        # 异步执行
        db_result = await db.run_query_async(sql)
        
        if db_result.get("error"):
             raise Exception(db_result["error"])
        
        json_result_str = db_result.get("json", "[]")
        json_result = json.loads(json_result_str)
        
        # 健壮性检查：确保 json_result 是列表，如果是 None 则转为空列表
        if json_result is None:
            json_result = []
        elif not isinstance(json_result, list):
            # 如果是字典（可能是错误对象），也将其包装为列表或仅处理空检查
            print(f"DEBUG: Unexpected json_result type: {type(json_result)}")
            if isinstance(json_result, dict) and "error" in json_result:
                raise Exception(json_result["error"])
            json_result = [] # 默认回退为空列表

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
        
        ai_msg_content = ""
        download_token = None
        if len(json_result) == 0:
            print(f"DEBUG: SQL executed successfully but returned 0 rows. SQL: {sql}")
            suggestion = await analyze_empty_result(sql, project_id)
            ai_msg_content = f"查询执行成功，但未找到任何匹配的数据。 {suggestion}"
            json_result_str = "[]"
        else:
            print(f"DEBUG: SQL returned {len(json_result)} rows.")
            preview_count = min(len(json_result), settings.PREVIEW_ROW_COUNT)
            preview = json_result[:preview_count]
            json_result_str = json.dumps(preview, ensure_ascii=False)
            ai_msg_content = f"查询成功，找到 {len(json_result)} 条记录。"
            try:
                r = get_redis_client()
                token = f"t2s:v1:download:{project_id}:{str(time.time())}"
                r.setex(token, settings.DOWNLOAD_TTL, json.dumps({"sql": sql, "project_id": project_id}))
                download_token = token
            except Exception as _:
                download_token = None
        return {
            "results": json_result_str,
            "messages": [AIMessage(content=ai_msg_content)],
            "error": None,
            "retry_count": 0,
            "download_token": download_token
        }
        
    except Exception as e:
        error_msg = str(e)
        # 错误类型分类
        def classify_error(msg: str) -> str:
            m = msg.lower()
            if "unknown column" in m or "column not found" in m or "no such column" in m or "undefined column" in m:
                return "column_not_found"
            if "unknown table" in m or "no such table" in m or "relation" in m and "does not exist" in m:
                return "table_not_found"
            if "syntax error" in m or "parse error" in m:
                return "syntax_error"
            if "does not exist" in m and "function" in m:
                return "function_not_found"
            if "operator does not exist" in m or "type mismatch" in m or "invalid input syntax" in m:
                return "type_mismatch"
            if "permission denied" in m or "read only" in m:
                return "permission"
            if "unknown column in 'field list'" in m or "ambiguous column" in m:
                return "ambiguous_or_field_list"
            if "unknown column" in m and "on clause" in m:
                return "join_invalid"
            return "unknown"
        err_type = classify_error(error_msg)
        if "read only" in error_msg.lower():
             error_msg = f"数据库错误: 数据库处于只读模式。请检查您的查询或数据库配置。 ({error_msg})"

        return {
            "error": error_msg,
            "results": f"SQL 执行失败: {error_msg}",
            "error_type": err_type
        }
