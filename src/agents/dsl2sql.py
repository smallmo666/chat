from langchain_core.prompts import ChatPromptTemplate
from src.state.state import AgentState
from src.utils.llm import get_llm
from src.utils.db import get_app_db

llm = get_llm()

def dsl_to_sql_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering dsl_to_sql_node")
    try:
        dsl = state.get("dsl")
        print(f"DEBUG: dsl_to_sql_node input dsl: {dsl}")
        
        # 获取数据库 Schema 信息
        # 优先使用 SelectTables 节点筛选出的相关 Schema
        schema_info = state.get("relevant_schema", "")
        
        if not schema_info:
            print("DEBUG: No relevant_schema found in dsl_to_sql_node")
            # Fallback
            try:
                app_db = get_app_db()
                full_schema_json = app_db.get_stored_schema_info()
                if len(full_schema_json) > 5000:
                    schema_info = full_schema_json[:5000] + "\n...(truncated)"
                else:
                    schema_info = full_schema_json
            except Exception as e:
                schema_info = "Schema info unavailable"
        
        system_prompt = (
            "你是一位 SQL 专家。将以下的 JSON DSL 转换为 MySQL 查询语句。\n"
            "数据库 Schema 信息如下:\n"
            "{schema_info}\n\n"
            "仅返回 SQL 字符串，不要包含 Markdown 格式。"
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{dsl}")
        ]).partial(schema_info=schema_info)
        
        chain = prompt | llm
        
        # Pass config to invoke to propagate callbacks
        invoke_args = {"dsl": dsl}
        print("DEBUG: Invoking LLM for SQL generation...")
        if config:
            result = chain.invoke(invoke_args, config=config)
        else:
            result = chain.invoke(invoke_args)
        
        sql = result.content.strip()
        print(f"DEBUG: SQL generated: {sql}")
        
        # 清理可能存在的 markdown 代码块标记
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()
            
        return {"sql": sql}
    except Exception as e:
        print(f"ERROR in dsl_to_sql_node: {e}")
        import traceback
        traceback.print_exc()
        raise e
