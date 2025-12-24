from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

from src.state.state import AgentState
from src.utils.llm import get_llm

llm = get_llm()

def analysis_node(state: AgentState) -> dict:
    """
    数据分析节点。
    根据 SQL 执行结果和用户查询，生成数据解读和洞察。
    """
    query = state["messages"][-1].content # Ideally find the last human message
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    sql = state.get("sql", "N/A")
    results = state.get("results", "No results found.")
    
    prompt = ChatPromptTemplate.from_template(
        "你是一个资深数据分析师。请根据以下信息进行数据解读和洞察分析。\n"
        "用户问题: {query}\n"
        "执行 SQL: {sql}\n"
        "查询结果:\n{results}\n\n"
        "请提供：\n"
        "1. **数据解读**：简要概括结果中的关键数据。\n"
        "2. **洞察分析**：发现数据背后的趋势、异常或业务含义（如果有）。\n"
        "请使用 Markdown 格式，适当使用加粗、列表等。\n"
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "query": query,
        "sql": sql,
        "results": results[:5000] # Truncate if too long
    })
    
    return {"analysis": response.content}
