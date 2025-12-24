from langchain_core.prompts import ChatPromptTemplate
from src.state.state import AgentState
from src.utils.llm import get_llm
from src.utils.schema_search import get_schema_searcher

llm = get_llm()

def table_qa_node(state: AgentState) -> dict:
    """
    表信息问答节点。
    回答关于数据库 Schema 的问题。
    """
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    searcher = get_schema_searcher()
    # 检索相关 Schema 上下文
    schema_context = searcher.search_relevant_tables(query, limit=5)
    
    prompt = ChatPromptTemplate.from_template(
        "你是一个数据库 Schema 助手。请根据提供的数据库 Schema 信息，回答用户关于表结构、字段含义的问题。\n"
        "Schema 信息:\n{schema}\n\n"
        "用户问题: {query}\n\n"
        "请直接回答，条理清晰。"
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "schema": schema_context,
        "query": query
    })
    
    return {"messages": [response]}
