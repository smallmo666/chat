from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.core.database import get_app_db
from src.domain.schema.value import get_value_searcher
import json

llm = None # Will be initialized in node

# --- Prompts ---
BASE_SYSTEM_PROMPT = """
你是一位 SQL 专家。将以下的 JSON DSL 转换为 MySQL 查询语句。
数据库 Schema 信息如下:
{schema_info}

{value_hints}

仅返回 SQL 字符串，不要包含 Markdown 格式。
"""

def dsl_to_sql_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering dsl_to_sql_node")
    try:
        project_id = config.get("configurable", {}).get("project_id") if config else None
        llm = get_llm(node_name="DSLtoSQL", project_id=project_id)
        
        dsl = state.get("dsl")
        print(f"DEBUG: dsl_to_sql_node input dsl: {dsl}")
        
        # --- Entity Linking / Value Correction ---
        value_hints = ""
        try:
            # 预处理 DSL 字符串，尝试清理 Markdown
            clean_dsl = dsl
            if "```json" in clean_dsl:
                clean_dsl = clean_dsl.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_dsl:
                clean_dsl = clean_dsl.split("```")[1].split("```")[0].strip()
                
            dsl_json = json.loads(clean_dsl)
            filters = dsl_json.get("filters", [])
            
            project_id = config.get("configurable", {}).get("project_id")
            value_searcher = get_value_searcher(project_id)
            
            hints = []
            for f in filters:
                if isinstance(f, dict) and "value" in f and isinstance(f["value"], str):
                    val = f["value"]
                    # 只有当值看起来像是一个模糊实体时才搜索 (简单的启发式：长度>1)
                    if len(val) > 1:
                        matches = value_searcher.search_similar_values(val, limit=3)
                        if matches:
                            match_strs = [f"'{m['value']}' (in {m['table']}.{m['column']})" for m in matches]
                            hints.append(f"用户输入值 '{val}' 可能对应数据库中的: {', '.join(match_strs)}")
            
            if hints:
                value_hints = "\n\n**实体链接建议 (Entity Linking Hints)**:\n" + "\n".join(hints) + "\n请优先使用上述建议中的精确值替换 DSL 中的模糊值。"
                print(f"DEBUG: Generated Entity Linking hints: {len(hints)} items")
                
        except Exception as e:
            print(f"DEBUG: Entity Linking failed (non-fatal): {e}")
        # -----------------------------------------
        
        # 获取数据库 Schema 信息
        schema_info = state.get("relevant_schema", "")
        
        if not schema_info:
            print("DEBUG: No relevant_schema found in dsl_to_sql_node")
            try:
                app_db = get_app_db()
                full_schema_json = app_db.get_stored_schema_info()
                if len(full_schema_json) > 5000:
                    schema_info = full_schema_json[:5000] + "\n...(truncated)"
                else:
                    schema_info = full_schema_json
            except Exception as e:
                schema_info = "Schema info unavailable"
        
        # 动态构建系统提示词
        system_prompt = BASE_SYSTEM_PROMPT

        # --- Retry Logic: Error Context ---
        error = state.get("error")
        if error:
            print(f"DEBUG: DSLtoSQL - Injecting error context: {error}")
            system_prompt += f"\n\n!!! 重要提示 !!!\n上一次生成的 SQL 执行错误：\n{error}\n请根据错误信息修正 SQL（例如：修复语法错误、列名错误）。"
        # ----------------------------------
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{dsl}")
        ]).partial(schema_info=schema_info, value_hints=value_hints)
        
        chain = prompt | llm
        
        # 传递 config 给 invoke 以传播回调
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
