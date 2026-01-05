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
   - 如果是 PostgreSQL:
     - 表名引用规则: 如果表名包含 schema (例如 "schema.table")，必须分别引用为 "schema"."table"。严禁使用 "schema.table"。
     - 列名引用规则: 使用双引号 "column_name"。
   - 如果是 MySQL:
     - 使用反引号 `table` 和 `column`。
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
        
        print(f"DEBUG: Detected DB Type: {db_type}")

        # --- 特殊处理: PostgreSQL 表名 ---
        # 如果是 PG，且 dsl 中包含 'schema.table' 格式，LLM 可能会生成 "schema.table" (错)
        # 我们需要提示 LLM 正确处理，或者在 prompt 中加强。
        # 这里我们在 System Prompt 中增加了更明确的 PG 引用规则。
        # -------------------------------

        # 2. Schema 信息获取 (增强版)
        schema_info = state.get("relevant_schema", "")
        if not schema_info:
            print("DEBUG: No relevant_schema found in state, attempting fallback inspection...")
            try:
                # 使用 run_in_executor 或 to_thread 避免阻塞
                # inspect_schema 目前是同步方法（内部创建临时 engine）
                
                # 关键修复：确保传递 project_id 相关的配置，如果需要的话。
                # 目前 inspect_schema 会自动发现库，但可能需要限制范围以减少开销。
                # 暂时保持全量或默认策略。
                
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
        
        # --- Schema 注入增强: 强制包含表名列表 ---
        # 即使 schema_info 很大被截断，我们至少要保证表名列表是完整的，
        # 这样 LLM 即使不知道字段，也能知道表是否存在，从而避免幻觉表名。
        # 这里我们简单解析一下 schema_info (如果是 json) 或者依赖 inspect_schema 的输出结构
        # ---------------------------------------

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
            
        # --- 强制修正 PostgreSQL 的 Schema 引用问题 ---
        # 无论 db_type 检测结果如何，只要发现 "schema.table" 格式的引用，都尝试修复
        # 因为 Postgres 驱动会抛出 "relation does not exist" 错误，说明底层确实是 PG
        if True: # 强制启用
            # 修复 FROM "schema.table" -> FROM "schema"."table"
            
            def fix_pg_schema_ref(match):
                full_ref = match.group(1) # e.g. "sports_events.races"
                if "." in full_ref:
                    print(f"DEBUG: Found quoted schema ref: {full_ref}")
                    parts = full_ref.replace('"', '').split('.')
                    if len(parts) == 2:
                        fixed = f'"{parts[0]}"."{parts[1]}"'
                        print(f"DEBUG: Fixing {match.group(0)} -> {fixed}")
                        return fixed
                return match.group(0)

            # 替换所有 "schema.table" 格式的引用
            sql = re.sub(r'"([^"]+\.[^"]+)"', fix_pg_schema_ref, sql)
            print(f"DEBUG: SQL after fix: {sql}")
        # ---------------------------------------------

        return {"sql": sql}
        
    except Exception as e:
        print(f"ERROR in dsl_to_sql_node: {e}")
        import traceback
        traceback.print_exc()
        raise e
