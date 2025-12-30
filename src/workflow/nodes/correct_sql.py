from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.core.llm import get_llm

llm = None # Will be initialized in node

class CorrectionResponse(BaseModel):
    fixed_sql: str = Field(..., description="The corrected SQL query")
    reasoning: str = Field(..., description="Explanation of the fix")

system_prompt = (
    "你是一个 SQL 调试专家。\n"
    "你的任务是根据数据库返回的错误信息，修复错误的 SQL 查询。\n\n"
    "错误信息:\n"
    "{error_message}\n\n"
    "错误的 SQL:\n"
    "{wrong_sql}\n\n"
    "请仔细分析错误原因（例如：列名拼写错误、GROUP BY 缺失、类型不匹配等），并输出修复后的 SQL。\n"
    "只输出修复后的 SQL，不要输出其他废话。"
)

def correct_sql_node(state: AgentState, config: dict = None) -> dict:
    """
    SQL 修正节点。
    """
    print("DEBUG: Entering correct_sql_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="CorrectSQL", project_id=project_id)
    
    wrong_sql = state.get("sql", "")
    error_message = state.get("error", "")
    retry_count = state.get("retry_count", 0)
    
    # 获取 Schema (可选，从 state 或 searcher)
    # 暂时只依赖错误信息，通常足够
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
    ]).partial(error_message=error_message, wrong_sql=wrong_sql)
    
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
