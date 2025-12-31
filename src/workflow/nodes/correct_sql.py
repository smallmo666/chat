from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.schema.search import get_schema_searcher

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

参考表结构 (Schema):
{schema_context}

请仔细分析错误原因（例如：列名拼写错误、GROUP BY 缺失、类型不匹配等），并利用提供的 Schema 信息找到正确的表名或列名。
只输出修复后的 SQL，不要输出其他废话。
"""

def correct_sql_node(state: AgentState, config: dict = None) -> dict:
    """
    SQL 修正节点。
    增强版：注入 Schema RAG 信息以辅助修复。
    """
    print("DEBUG: Entering correct_sql_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="CorrectSQL", project_id=project_id)
    
    wrong_sql = state.get("sql", "")
    error_message = state.get("error", "")
    retry_count = state.get("retry_count", 0)
    
    # 获取 Schema RAG 上下文
    schema_context = "暂无 Schema 信息"
    try:
        searcher = get_schema_searcher(project_id)
        
        # 策略 1: 使用错误的 SQL 进行检索 (针对语法错误或部分正确的 SQL)
        search_query = wrong_sql
        
        # 策略 2: 如果有重写后的用户查询，结合使用 (针对表名完全错误的 SQL)
        rewritten_query = state.get("rewritten_query")
        if rewritten_query:
            # 组合查询，增加召回率
            search_query = f"{wrong_sql} {rewritten_query}"
            print(f"DEBUG: CorrectSQL using combined search query.")
            
        # 检索最相关的表
        schema_context = searcher.search_relevant_tables(search_query, limit=3)
        print("DEBUG: Retrieved schema context for correction.")
    except Exception as e:
        print(f"Failed to retrieve schema for correction: {e}")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", BASE_SYSTEM_PROMPT),
    ]).partial(error_message=error_message, wrong_sql=wrong_sql, schema_context=schema_context)
    
    chain = prompt | llm.with_structured_output(CorrectionResponse)
    
    try:
        result = chain.invoke({})
        fixed_sql = result.fixed_sql
        reasoning = result.reasoning
        
        print(f"DEBUG: Fixed SQL: {fixed_sql}")
        print(f"DEBUG: Reasoning: {reasoning}")
        
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
