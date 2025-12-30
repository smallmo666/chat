from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

from src.workflow.state import AgentState
from src.core.llm import get_llm

llm = None # Will be initialized in node

def analysis_node(state: AgentState, config: dict = None) -> dict:
    """
    数据分析节点。
    根据 SQL 执行结果和用户查询，生成数据解读和洞察。
    """
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="DataAnalysis", project_id=project_id)
    query = state["messages"][-1].content # 理想情况下找到最后一条用户消息
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    # 如果有重写后的查询（包含上下文），优先使用它作为分析的上下文
    rewritten_query = state.get("rewritten_query")
    if rewritten_query:
        query = rewritten_query
            
    sql = state.get("sql", "N/A")
    results = state.get("results", "No results found.")
    
    prompt = ChatPromptTemplate.from_template(
        "你是一个资深数据分析师。请根据以下信息进行数据解读和洞察分析。\n"
        "用户问题: {query}\n"
        "执行 SQL: {sql}\n"
        "查询结果 (JSON 格式):\n{results}\n\n"
        "请遵循以下要求：\n"
        "1. **数据展示**：如果结果包含多行数据，**必须使用 Markdown 表格**展示明细，不要使用列表。如果数据量较大，展示前 10-20 条即可，并说明已截断。\n"
        "2. **关键结论**：回答用户问题的核心结论。\n"
        "3. **洞察分析**：发现数据背后的趋势、异常或业务含义（如果有）。\n"
        "请使用 Markdown 格式，保持专业、清晰。\n"
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "query": query,
        "sql": sql,
        "results": results[:5000] # 如果太长则截断
    })
    
    return {"analysis": response.content}
