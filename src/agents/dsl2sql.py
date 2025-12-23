from langchain_core.prompts import ChatPromptTemplate
from src.state.state import AgentState
from src.utils.llm import get_llm
from src.utils.db import get_app_db

llm = get_llm()

def dsl_to_sql_node(state: AgentState) -> dict:
    dsl = state.get("dsl")
    
    # 获取数据库 Schema 信息 (从 AppDB 获取存储的元数据)
    try:
        app_db = get_app_db()
        schema_info = app_db.get_stored_schema_info()
    except Exception as e:
        # schema_info = "无法获取数据库 Schema: " + str(e)
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
    result = chain.invoke({"dsl": dsl})
    
    sql = result.content.strip()
    # 清理可能存在的 markdown 代码块标记
    if "```sql" in sql:
        sql = sql.split("```sql")[1].split("```")[0].strip()
    elif "```" in sql:
        sql = sql.split("```")[1].split("```")[0].strip()
        
    return {"sql": sql}
