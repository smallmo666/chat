import asyncio
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.schema.search import get_schema_searcher

async def table_qa_node(state: AgentState, config: dict = None) -> dict:
    """
    智能问答节点 (Table QA) - Async。
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
            
    # 异步检索相关 Schema 信息
    schema_context = "暂无相关表结构信息。"
    all_tables_context = "暂无表列表信息。"

    def _search_schema():
        try:
            # 移动到线程内以避免初始化阻塞
            searcher = get_schema_searcher(project_id)
            relevant = searcher.search_relevant_tables(query, limit=10)
            
            # 获取所有表名 (用于回答"有多少张表"等宏观问题)
            all_tables = []
            if searcher.all_table_metadata:
                all_tables = sorted(list(searcher.all_table_metadata.keys()))
                # 限制数量防止 Context 溢出 (虽然表名一般不长，但以防万一)
                if len(all_tables) > 500:
                    all_tables = all_tables[:500]
                    all_tables.append(f"... (共 {len(searcher.all_table_metadata)} 张表，已截断)")
            
            return {
                "relevant": relevant,
                "all_tables": ", ".join(all_tables)
            }
        except Exception as e:
            print(f"TableQA: Failed to retrieve schema: {e}")
            return None

    try:
        # 使用 asyncio.to_thread 包装同步检索
        result = await asyncio.to_thread(_search_schema)
        if result:
            schema_context = result["relevant"]
            all_tables_context = result["all_tables"]
    except Exception as e:
        print(f"TableQA: Failed to retrieve schema: {e}")
        
    prompt = ChatPromptTemplate.from_template(
        "你是一个数据库元数据专家。请根据用户的提问和提供的 Schema 信息，解答关于数据库结构的问题。\n"
        "用户问题: {query}\n\n"
        "数据库全量表名列表:\n{all_tables_context}\n\n"
        "最相关的详细 Schema:\n{schema_context}\n\n"
        "请遵循以下要求：\n"
        "1. **准确性**：只根据提供的 Schema 回答，不要编造字段或表。\n"
        "2. **清晰性**：必须使用 **Markdown 表格** 清晰展示表名、字段名和注释，以便前端渲染。\n"
        "3. **专业性**：如果 Schema 中包含注释，请务必解释字段的业务含义。\n"
        "4. **范围**：如果用户问的问题超出 Schema 范围，请诚实回答“未在相关表中找到信息”。\n"
        "5. **宏观问题**：如果用户询问有多少张表或列出所有表，请参考“数据库全量表名列表”回答。\n"
        "6. **容错性**：如果用户使用的术语与 Schema 不完全一致（例如“库存” vs “stock_qty”），请尝试进行语义匹配并解释你的推断。\n"
    )
    
    chain = prompt | llm
    # 异步调用 LLM
    response = await chain.ainvoke({
        "query": query,
        "schema_context": schema_context,
        "all_tables_context": all_tables_context
    })
    
    return {
        "messages": [AIMessage(content=response.content)]
    }
