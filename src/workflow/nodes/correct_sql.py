import asyncio
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.schema.search import get_schema_searcher
from src.core.database import get_query_db
from src.core.sql_security import is_safe_sql

llm = None # Will be initialized in node

class CorrectionResponse(BaseModel):
    fixed_sql: str = Field(..., description="The corrected SQL query")
    reasoning: str = Field(..., description="Explanation of the fix")

# --- Prompts ---
BASE_SYSTEM_PROMPT = """
你是一个 SQL 调试专家。
你的任务是根据数据库返回的错误信息，修复错误的 SQL 查询。

错误信息:
{error_message}

错误的 SQL:
{wrong_sql}

数据库方言: {dialect}
(请确保使用符合该方言的语法，例如 PostgreSQL 的引号规则或 MySQL 的反引号规则)

参考表结构 (Schema):
{schema_context}

请仔细分析错误原因（例如：列名拼写错误、GROUP BY 缺失、类型不匹配等），并利用提供的 Schema 信息找到正确的表名或列名。
如果错误提示“Column not found”且你在 Schema 中发现了相似的列名，请大胆修正。
只输出修复后的 SQL，不要输出其他废话。
"""

async def correct_sql_node(state: AgentState, config: dict = None) -> dict:
    """
    SQL 修正节点 (Async)。
    增强版：注入 Schema RAG 信息以辅助修复，支持动态方言。
    **自愈增强**: 当检测到 'Column not found' 时，主动探测 Schema。
    **安全增强**: 对修复后的 SQL 进行安全检查。
    """
    print("DEBUG: Entering correct_sql_node (Async)")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="CorrectSQL", project_id=project_id)
    
    wrong_sql = state.get("sql", "")
    error_message = state.get("error", "")
    retry_count = state.get("retry_count", 0)
    
    # 1. 获取数据库类型 (Dialect)
    db_type = "MySQL" # 默认
    query_db = None
    try:
        query_db = get_query_db(project_id)
        if query_db.type == "postgresql":
            db_type = "PostgreSQL"
        elif query_db.type == "mysql":
            db_type = "MySQL"
    except Exception as e:
        print(f"DEBUG: Failed to detect DB type, defaulting to MySQL: {e}")

    # 2. Schema 探测 (Self-Healing Logic)
    schema_context = ""
    is_column_error = "column" in error_message.lower() or "field" in error_message.lower()
    
    if is_column_error and query_db:
        print("DEBUG: CorrectSQL - Detected Column/Field error, initiating Schema Probe...")
        try:
            # 尝试从错误信息或 SQL 中提取表名
            # 简单的正则提取，假设 FROM table_name 或 JOIN table_name
            # 这只是一个简单的启发式
            potential_tables = re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)', wrong_sql, re.IGNORECASE)
            
            if potential_tables:
                print(f"DEBUG: Probing tables: {potential_tables}")
                # 使用 query_db 的 inspect_schema 实时获取这些表的最新结构
                # inspect_schema 是同步的，需要在 thread 中运行
                probe_config = {"tables": list(set(potential_tables))} # 去重
                
                realtime_schema_json = await asyncio.to_thread(query_db.inspect_schema, probe_config)
                
                # 格式化为 Context 字符串
                import json
                schema_dict = json.loads(realtime_schema_json)
                
                schema_context_lines = ["*** REAL-TIME SCHEMA PROBE RESULT ***"]
                for table, info in schema_dict.items():
                    cols = [f"{c['name']} ({c['type']})" for c in info.get('columns', [])]
                    schema_context_lines.append(f"Table: {table}")
                    schema_context_lines.append(f"Columns: {', '.join(cols)}")
                
                schema_context = "\n".join(schema_context_lines)
                print(f"DEBUG: Schema Probe successful. Context len: {len(schema_context)}")
        except Exception as e:
            print(f"DEBUG: Schema Probe failed: {e}")

    # 3. 如果探测失败或不是列错误，回退到 RAG 检索
    if not schema_context:
        try:
            def _search_schema():
                searcher = get_schema_searcher(project_id)
                # 策略: 使用错误的 SQL 进行检索
                search_query = wrong_sql
                return searcher.search_relevant_tables(search_query, limit=3)

            schema_context = await asyncio.to_thread(_search_schema)
            print("DEBUG: Retrieved schema context from RAG.")
        except Exception as e:
            print(f"Failed to retrieve schema from RAG: {e}")
            schema_context = "暂无 Schema 信息"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", BASE_SYSTEM_PROMPT),
    ]).partial(
        error_message=error_message, 
        wrong_sql=wrong_sql, 
        schema_context=schema_context,
        dialect=db_type
    )
    
    chain = prompt | llm.with_structured_output(CorrectionResponse)
    
    try:
        # 异步调用 LLM
        result = await chain.ainvoke({})
        fixed_sql = result.fixed_sql
        reasoning = result.reasoning
        
        print(f"DEBUG: Fixed SQL: {fixed_sql}")
        print(f"DEBUG: Reasoning: {reasoning}")
        
        # 安全检查 (Guardrails)
        if not is_safe_sql(fixed_sql):
            print("Security Alert: Auto-corrected SQL failed safety check.")
            return {
                "retry_count": retry_count + 1,
                "error": "Auto-corrected SQL was rejected by security policy."
            }

        return {
            "sql": fixed_sql,
            "error": None, # 清除错误
            "retry_count": retry_count + 1,
            "messages": [AIMessage(content=f"🛠️ SQL 执行报错，正在尝试自动修复...\n原因: {reasoning}")]
        }
    except Exception as e:
        print(f"Correction failed: {e}")
        # 如果修复也失败了，增加计数，让 Supervisor 决定（可能会最终放弃）
        return {
            "retry_count": retry_count + 1,
            "error": f"Auto-correction failed: {e}" 
        }
