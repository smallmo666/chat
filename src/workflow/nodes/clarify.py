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
    if state.get("interrupt_pending"):
        return {"intent_clear": False, "last_executed_node": "ClarifyIntent"}

    # 获取用户 ID 和 Project ID
    configurable = config.get("configurable", {}) if config else {}
    thread_id = configurable.get("thread_id", "default_thread")
    project_id = configurable.get("project_id")
    
    # 获取真实 User ID (优先使用显式传入的 user_id)
    # 之前错误地使用了 thread_id 作为 user_id，导致记忆无法跨会话共享
    raw_user_id = configurable.get("user_id")
    # Mem0 需要 string 类型的 user_id
    user_id = str(raw_user_id) if raw_user_id else thread_id

    llm = get_llm(node_name="ClarifyIntent", project_id=project_id)
    
    messages = state["messages"]
    last_msg = messages[-1].content
    
    # 获取最近的对话历史 (最多5轮)，辅助理解上下文 (如代词 "它")
    history_msgs = messages[-10:-1] if len(messages) > 1 else []
    history_text = "\n".join([f"{m.type}: {m.content}" for m in history_msgs]) if history_msgs else "无历史对话"
    
    # 定义异步检索任务
    def _get_memory():
        try:
            memory_client = get_memory()
            # 检索原始 Query 以及关键词
            mem_results = memory_client.search(user_id=user_id, query=last_msg, limit=5)
            
            # Robust extraction of memory content
            if isinstance(mem_results, dict) and "results" in mem_results:
                 mem_results = mem_results["results"]
            
            final_results = []
            if isinstance(mem_results, list):
                for m in mem_results:
                    if isinstance(m, dict):
                        final_results.append(m.get("memory", str(m)))
                    else:
                        final_results.append(str(m))
            return final_results
        except Exception as e:
            print(f"Clarify: Failed to retrieve memory: {e}")
            return []

    def _get_schema():
        try:
            # 移动到线程内以避免初始化阻塞
            searcher = get_schema_searcher(project_id)
            # 检索 Top-5 表，让 LLM 知道数据库里大概有什么
            # 使用混合检索 (Hybrid Search)
            return searcher.search_relevant_tables(last_msg, limit=5)
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
        "你需要结合【数据库 Schema】和【对话历史】来判断用户的术语是否明确。\n\n"
        "### 数据库 Schema (仅供参考):\n"
        "{schema_context}\n\n"
        "### 对话历史 (Context):\n"
        "{history_text}\n\n"
        "### 用户历史记忆/偏好 (重要):\n"
        "{memory_context}\n\n"
        "### 规则:\n"
        "1. **优先使用记忆**：如果用户的意图在历史记忆中已经澄清过（例如记忆中显示 '销量' = 'sales_amount'），请直接判定为 CLEAR，不要重复提问。\n"
        "2. **上下文理解**：如果用户使用了代词（如 '它'、'这些'），请结合对话历史解析其实际指代。如果能解析清楚，判定为 CLEAR。\n"
        "3. 如果意图清晰（用户的问题可以映射到上述 Schema 中的表和字段），请严格返回 JSON: {{\"status\": \"CLEAR\"}}\n"
        "4. 如果意图不清晰（例如：用户查询'销量'但Schema中只有'amount'，或者用户未指定时间范围且Schema中包含时间字段），请返回 JSON:\n"
        "   {{\"status\": \"AMBIGUOUS\", \"question\": \"简短友好的澄清问题\", \"options\": [\"选项1\", \"选项2\", ...], \"type\": \"select\"}}\n"
        "   - options 应该基于 Schema 中的列名或常见业务术语。\n"
        "   - type 可以是 'select' (单选) 或 'multiple' (多选)。\n"
        "5. **歧义检测**：如果用户的术语对应 Schema 中的多个字段（如 'user' 可能是 'user_id' 或 'username'），且没有历史记忆可参考，请提供选项让用户选择。\n"
        "6. 必须只返回合法的 JSON 字符串，不要包含 Markdown 标记。\n"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ]).partial(memory_context=memory_context, schema_context=schema_context, history_text=history_text)
    
    chain = prompt | llm
    
    # 异步调用 LLM
    result = await chain.ainvoke({"query": last_msg}, config=config)
    content = result.content.strip()
    
    # 清理 Markdown 代码块 (以防万一)
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    print(f"DEBUG: ClarifyIntent Raw Result: {content}")
    
    import json
    try:
        parsed = json.loads(content)
        if parsed.get("status") == "CLEAR":
            return {"intent_clear": True, "last_executed_node": "ClarifyIntent"}
        else:
            payload = {
                "question": parsed.get("question", ""),
                "options": parsed.get("options", []),
                "type": parsed.get("type", "select")
            }
            return {
                "messages": [AIMessage(content=content)],
                "intent_clear": False,
                "clarify": payload,
                "last_executed_node": "ClarifyIntent"
            }
    except json.JSONDecodeError:
        print("Clarify: Failed to parse JSON, falling back to text.")
        # 回退逻辑：假设内容就是问题
        if "CLEAR" in content.upper() and len(content) < 20:
             return {"intent_clear": True, "last_executed_node": "ClarifyIntent"}
        return {
            "messages": [AIMessage(content=content)],
            "intent_clear": False,
            "last_executed_node": "ClarifyIntent"
        }
