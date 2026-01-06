import re
import asyncio
import json
from src.workflow.state import AgentState
from src.core.database import get_query_db
from src.core.dsl.compiler import DSLCompiler

async def dsl_to_sql_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering dsl_to_sql_node (Async) - Using Code Compiler")
    try:
        project_id = config.get("configurable", {}).get("project_id") if config else None
        
        dsl_str = state.get("dsl")
        print(f"DEBUG: dsl_to_sql_node input dsl: {dsl_str}")
        
        # 1. 获取数据库类型 (Dialect)
        db_type = "mysql" # 默认
        try:
            query_db = get_query_db(project_id)
            if query_db.type == "postgresql":
                db_type = "postgresql"
            elif query_db.type == "mysql":
                db_type = "mysql"
        except Exception as e:
            print(f"DEBUG: Failed to detect DB type, defaulting to MySQL: {e}")
        
        print(f"DEBUG: Detected DB Type: {db_type}")

        # 2. 解析 DSL JSON
        try:
            # 清理可能的 Markdown
            cleaned_dsl = dsl_str.strip()
            if "```json" in cleaned_dsl:
                cleaned_dsl = cleaned_dsl.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_dsl:
                cleaned_dsl = cleaned_dsl.split("```")[1].split("```")[0].strip()
            
            # 尝试直接解析
            try:
                dsl_json = json.loads(cleaned_dsl)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取最外层的大括号内容
                # 这能处理 "Here is the JSON: {...} some other text" 的情况
                print("DEBUG: JSON parse failed, attempting regex extraction...")
                match = re.search(r'(\{.*\})', cleaned_dsl, re.DOTALL)
                if match:
                    json_candidate = match.group(1)
                    dsl_json = json.loads(json_candidate)
                else:
                    raise ValueError("No JSON object found in output")
                    
        except Exception as e:
            print(f"Error parsing DSL JSON: {e}")
            raise ValueError(f"Invalid JSON DSL format. Content: {dsl_str[:100]}...")
            
        # 3. 编译 SQL
        compiler = DSLCompiler(dialect=db_type)
        try:
            sql = compiler.compile(dsl_json)
            print(f"DEBUG: Compiled SQL: {sql}")
        except Exception as e:
            print(f"Error compiling SQL: {e}")
            raise ValueError(f"DSL Compilation Failed: {e}")

        return {"sql": sql}
        
    except Exception as e:
        print(f"ERROR in dsl_to_sql_node: {e}")
        import traceback
        traceback.print_exc()
        raise e
