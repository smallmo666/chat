import asyncio
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.memory.short_term import get_memory
from src.domain.schema.search import get_schema_searcher

async def clarify_intent_node(state: AgentState, config: dict = None) -> dict:
    """
    意图澄清节点 (Async)。
    使用 LLM 分析用户意图。如果意图不清晰，则生成澄清问题。
    集成长期记忆（用户偏好）和 Schema RAG（数据库结构）以辅助判断。
    """
    print("DEBUG: Entering clarify_intent_node (Async)")

    # 获取用户 ID 和 Project ID
    user_id = config.get("configurable", {}).get("thread_id", "default_user") if config else "default_user"
    project_id = config.get("configurable", {}).get("project_id") if config else None

    llm = get_llm(node_name="ClarifyIntent", project_id=project_id)
    
    messages = state["messages"]
    last_msg = messages[-1].content
    
    # 定义异步检索任务
    def _get_memory():
        try:
            memory_client = get_memory()
            mem_results = memory_client.search(user_id=user_id, query=last_msg, limit=3)
            return [m["memory"] for m in mem_results] if mem_results else []
        except Exception as e:
            print(f"Clarify: Failed to retrieve memory: {e}")
            return []

    def _get_schema():
        try:
            # 移动到线程内以避免初始化阻塞
            searcher = get_schema_searcher(project_id)
            # 检索 Top-5 表，让 LLM 知道数据库里大概有什么
            return searcher.search(last_msg, top_k=5)
        except Exception as e:
            print(f"Clarify: Failed to retrieve schema: {e}")
            return None

    # 并发执行检索
    results = await asyncio.gather(
        asyncio.to_thread(_get_memory),
        asyncio.to_thread(_get_schema)
    )
    
    memories = results[0]
    schema_info = results[1]

    memory_context = "\n".join([f"- {m}" for m in memories]) if memories else "无历史记录"
    schema_context = schema_info if schema_info else "暂无数据库表结构信息。"

    system_prompt = (
        "你是一个 Text2SQL 的意图分析专家。\n"
        "你的任务是判断用户的输入是否包含足够的信息来构建 SQL 查询。\n"
        "你需要结合【数据库 Schema】来判断用户的术语是否明确。\n\n"
        "### 数据库 Schema (仅供参考):\n"
        "{schema_context}\n\n"
        "### 用户历史记忆/偏好:\n"
        "{memory_context}\n\n"
        "### 规则:\n"
        "1. 如果意图清晰（用户的问题可以映射到上述 Schema 中的表和字段，或者可以通过历史记忆补全），请只输出 'CLEAR'。\n"
        "2. 如果意图不清晰（例如：用户查询'销量'但Schema中只有'amount'，或者用户未指定时间范围且Schema中包含时间字段），请输出一个简短、友好的澄清问题。\n"
        "3. **歧义检测**：如果用户的术语对应 Schema 中的多个字段（如 'user' 可能是 'user_id' 或 'username'），请反问用户。\n"
        "4. 澄清问题应该引导用户使用 Schema 中存在的术语。\n"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ]).partial(memory_context=memory_context, schema_context=schema_context)
    
    chain = prompt | llm
    
    # 异步调用 LLM
    result = await chain.ainvoke({"query": last_msg}, config=config)
    content = result.content.strip()
    
    print(f"DEBUG: ClarifyIntent Result: {content}")
    
    if "CLEAR" in content.upper() and len(content) < 10:
        return {"intent_clear": True}
    else:
        # 如果不是 CLEAR，说明是澄清问题。
        # 我们将问题作为 AIMessage 返回，并标记意图为不清晰。
        return {
            "messages": [AIMessage(content=content)],
            "intent_clear": False
        }
