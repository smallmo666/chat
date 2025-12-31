import re
import asyncio
from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.core.database import get_query_db

# --- Prompts ---
BASE_SYSTEM_PROMPT = """
你是一位 SQL 专家。请将以下的 JSON DSL 转换为标准的 {dialect} 查询语句。
数据库 Schema:
{schema_info}

规则:
1. 仅返回 SQL 字符串。不要包含 Markdown 或任何解释。
2. 使用标准的 {dialect} 语法。
   - 如果是 PostgreSQL，请使用双引号 `"` 包裹表名和列名（如果需要）。
   - 如果是 MySQL，请使用反引号 ` ` ` 包裹表名和列名。
3. 相信 DSL 中的值，它们已经被修正过了。
"""

async def dsl_to_sql_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering dsl_to_sql_node (Async)")
    try:
        project_id = config.get("configurable", {}).get("project_id") if config else None
        llm = get_llm(node_name="DSLtoSQL", project_id=project_id)
        
        dsl = state.get("dsl")
        print(f"DEBUG: dsl_to_sql_node input dsl: {dsl}")
        
        # 1. 获取数据库类型 (Dialect)
        db_type = "MySQL" # 默认
        try:
            query_db = get_query_db(project_id)
            if query_db.type == "postgresql":
                db_type = "PostgreSQL"
            elif query_db.type == "mysql":
                db_type = "MySQL"
        except Exception as e:
            print(f"DEBUG: Failed to detect DB type, defaulting to MySQL: {e}")

        # 2. Schema 信息获取 (增强版)
        schema_info = state.get("relevant_schema", "")
        if not schema_info:
            print("DEBUG: No relevant_schema found in state, attempting fallback inspection...")
            try:
                # 使用 run_in_executor 或 to_thread 避免阻塞
                # inspect_schema 目前是同步方法（内部创建临时 engine）
                schema_json = await asyncio.to_thread(query_db.inspect_schema)
                
                # 简单截断以防 Context Window 溢出
                # 更好的做法是基于 Token 计算，这里先用字符长度兜底
                if len(schema_json) > 10000:
                    schema_info = schema_json[:10000] + "\n...(truncated)"
                else:
                    schema_info = schema_json
            except Exception as e:
                print(f"DEBUG: Schema inspection failed: {e}")
                schema_info = "Schema info unavailable"
        
        # 3. 构建 Prompt
        system_prompt = BASE_SYSTEM_PROMPT

        # 重试逻辑：错误上下文
        error = state.get("error")
        if error:
            print(f"DEBUG: DSLtoSQL - Injecting error context: {error}")
            system_prompt += f"\n\n!!! 严重警告 !!!\n上一次生成的 SQL 导致了错误:\n{error}\n请根据错误修复 SQL (例如: 修复语法错误或列名错误)。"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{dsl}")
        ]).partial(schema_info=schema_info, dialect=db_type)
        
        chain = prompt | llm
        
        print(f"DEBUG: Invoking LLM for SQL generation (Dialect: {db_type})...")
        # 异步调用 LLM
        result = await chain.ainvoke({"dsl": dsl}, config=config)
        
        sql = result.content.strip()
        print(f"DEBUG: SQL generated: {sql}")
        
        # 清理 Markdown
        match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", sql, re.DOTALL)
        if match:
            sql = match.group(1).strip()
            
        return {"sql": sql}
        
    except Exception as e:
        print(f"ERROR in dsl_to_sql_node: {e}")
        import traceback
        traceback.print_exc()
        raise e
