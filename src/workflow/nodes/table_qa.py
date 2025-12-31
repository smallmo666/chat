from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.schema.search import get_schema_searcher

def table_qa_node(state: AgentState, config: dict = None) -> dict:
    """
    智能问答节点 (Table QA)。
    专门处理元数据查询（如“这个表有什么字段”、“status 字段是什么意思”）。
    直接检索 Schema RAG 并回答，不生成 SQL。
    """
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="TableQA", project_id=project_id)
    
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    # 检索相关 Schema 信息
    schema_context = "暂无相关表结构信息。"
    try:
        searcher = get_schema_searcher(project_id)
        # 检索 Top-10 表，尽可能提供丰富的元数据
        schema_info = searcher.search_relevant_tables(query, limit=10)
        if schema_info:
            schema_context = schema_info
    except Exception as e:
        print(f"TableQA: Failed to retrieve schema: {e}")
        
    prompt = ChatPromptTemplate.from_template(
        "你是一个数据库元数据专家。请根据用户的提问和提供的 Schema 信息，解答关于数据库结构的问题。\n"
        "用户问题: {query}\n\n"
        "相关数据库 Schema:\n{schema_context}\n\n"
        "请遵循以下要求：\n"
        "1. **准确性**：只根据提供的 Schema 回答，不要编造字段或表。\n"
        "2. **清晰性**：必须使用 **Markdown 表格** 清晰展示表名、字段名和注释，以便前端渲染。\n"
        "3. **专业性**：如果 Schema 中包含注释，请务必解释字段的业务含义。\n"
        "4. **范围**：如果用户问的问题超出 Schema 范围，请诚实回答“未在相关表中找到信息”。\n"
        "5. **容错性**：如果用户使用的术语与 Schema 不完全一致（例如“库存” vs “stock_qty”），请尝试进行语义匹配并解释你的推断。\n"
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "query": query,
        "schema_context": schema_context
    })
    
    return {
        "messages": [AIMessage(content=response.content)]
    }
