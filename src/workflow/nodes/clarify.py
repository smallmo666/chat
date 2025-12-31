from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.workflow.state import AgentState
from src.core.llm import get_llm
from src.domain.memory.short_term import get_memory
from src.domain.schema.search import get_schema_searcher

llm = None # Will be initialized in node

def clarify_intent_node(state: AgentState, config: dict = None) -> dict:
    """
    意图澄清节点。
    使用 LLM 分析用户意图，如果意图不清晰，则生成澄清问题。
    集成长期记忆：在分析意图时参考用户的历史偏好。
    集成 Schema RAG：在分析意图时参考数据库的真实表结构，避免幻觉。
    """
    print("DEBUG: Entering clarify_intent_node")

    # 获取用户 ID 和 Project ID
    user_id = config.get("configurable", {}).get("thread_id", "default_user") if config else "default_user"
    project_id = config.get("configurable", {}).get("project_id") if config else None

    llm = get_llm(node_name="ClarifyIntent", project_id=project_id)
    
    messages = state["messages"]
    
    # 获取最后一条消息
    last_msg = messages[-1].content
    
    # 1. 检索长期记忆
    memories = []
    try:
        memory_client = get_memory()
        mem_results = memory_client.search(user_id=user_id, query=last_msg, limit=3)
        memories = [m["memory"] for m in mem_results] if mem_results else []
    except Exception as e:
        print(f"Clarify: Failed to retrieve memory: {e}")
        pass

    memory_context = "\n".join([f"- {m}" for m in memories]) if memories else "无历史记录"
    
    # 2. 检索相关 Schema (Context-Aware)
    schema_context = "暂无数据库表结构信息。"
    try:
        searcher = get_schema_searcher(project_id)
        # 检索 Top-5 表，让 LLM 知道数据库里大概有什么
        schema_info = searcher.search(last_msg, top_k=5)
        if schema_info:
            schema_context = schema_info
    except Exception as e:
        print(f"Clarify: Failed to retrieve schema: {e}")

    system_prompt = (
        "你是一个 Text2SQL 的意图分析专家。\n"
        "你的任务是判断用户的输入是否包含足够的信息来构建 SQL 查询。\n"
        "你需要结合【数据库 Schema】来判断用户的术语是否明确。\n\n"
        "### 数据库 Schema (仅供参考):\n"
        "{schema_context}\n\n"
        "### 用户历史记忆/偏好:\n"
        "{memory_context}\n\n"
        "### 规则:\n"
        "1. 如果意图清晰（用户的问题可以映射到上述 Schema 中的表和字段），或者可以通过历史记忆补全，请只输出 'CLEAR'。\n"
        "2. 如果意图不清晰（例如：用户查询'销量'但Schema中只有'amount'，或者用户未指定时间范围且Schema中包含时间字段），请输出一个简短、友好的澄清问题。\n"
        "3. **歧义检测**：如果用户的术语对应 Schema 中的多个字段（如 'user' 可能是 'user_id' 或 'username'），请反问用户。\n"
        "4. 澄清问题应该引导用户使用 Schema 中存在的术语。\n"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ]).partial(memory_context=memory_context, schema_context=schema_context)
    
    chain = prompt | llm
    result = chain.invoke({"query": last_msg}, config=config)
    content = result.content.strip()
    
    print(f"DEBUG: ClarifyIntent Result: {content}")
    
    if "CLEAR" in content.upper() and len(content) < 10:
        return {"intent_clear": True}
    else:
        # 如果不是 CLEAR，说明是澄清问题
        # 我们将问题返回给用户，并标记意图未澄清
        # CRITICAL FIX: 必须中断 Graph 执行，等待用户回复。
        # 通过不设置 'next' 或设置 next="FINISH" (取决于 Supervisor 逻辑)
        # 这里我们假设 Supervisor 看到 intent_clear=False 会终止，或者我们显式返回 next="FINISH"
        # 更好的方式是：让 Supervisor 知道如果是 ClarifyIntent 且 intent_clear=False，则 FINISH。
        # 但为了安全，我们在这里也可以暗示。
        # 不过，节点返回的 dict 是用来更新 State 的。
        # 如果我们在这里返回 next="FINISH"，Supervisor 可能会覆盖它，因为 Supervisor 是下一个节点。
        # 等等，图结构是 ClarifyIntent -> Supervisor。
        # Supervisor 的逻辑是：如果 intent_clear=False -> ClarifyIntent (LOOP!)。
        # 所以必须修改 Supervisor 的逻辑，或者在这里做 Hack。
        # 正确的做法是：ClarifyIntent 节点不直接决定流程，而是通过 State 通知 Supervisor。
        # 我们需要修改 Supervisor，当 intent_clear=False 时，实际上应该 FINISH 并等待 Human Input。
        # 但在 LangGraph 中，等待 Human Input 通常意味着中断 (interrupt)。
        # 简单起见，我们在这里返回消息，并让 Supervisor 意识到这一点。
        # 实际上，如果 intent_clear=False，我们希望系统停止。
        # 让我们在 State 中增加一个标志 'require_human_input'？
        # 或者，我们修改 Supervisor，如果 intent_clear=False，则路由到 END。
        
        # 既然我们不能改 Supervisor (在本次 tool call 中)，我们只能依赖 Supervisor 的现有逻辑。
        # 让我们看看 Supervisor 的代码 (已读过)：
        # Supervisor 逻辑: next = plan[current_index]["node"]
        # 它似乎不看 intent_clear！
        # 只要 Plan 里有 ClarifyIntent，它就会执行。
        # 这里的 ClarifyIntent 是作为一个 Plan Step 吗？
        # 是的，Planner 可能会生成 [{"node": "ClarifyIntent"}]。
        # 如果 ClarifyIntent 执行完了，current_step_index + 1。
        # 如果 Plan 只有这一步，Supervisor 会看到 index >= len(plan)，然后 FINISH。
        # 所以，如果 Planner 生成了 ClarifyIntent，它只执行一次，然后结束。
        # 这是正确的！
        # 但是，如果 ClarifyIntent 发现意图不清，它应该生成问题并结束。
        # 现在的代码：return intent_clear=False。
        # Supervisor: current_step_index + 1 -> FINISH.
        # 所以循环问题可能不存在？
        # 除非 Planner 在 intent_clear=False 时又被调用了？
        # 通常 Flow 是: Planner -> Supervisor -> ClarifyIntent -> Supervisor -> FINISH.
        # 然后用户回复 -> Planner (新的) -> ...
        # 所以逻辑是通的。
        # 唯一的问题是：如果 intent_clear=True，我们希望 Planner 继续规划后续步骤吗？
        # 目前 Planner 是静态生成的。如果 Planner 生成了 [ClarifyIntent]，它就只做这个。
        # 如果 intent_clear=True，说明 Planner 判断错了（以为不清其实清），或者 LLM 自动补全了。
        # 这时我们希望继续执行查询。但 Plan 已经结束了。
        # 这意味着用户需要再次输入（即使意图已清），这体验不好。
        # 不过作为 MVP，这可以接受。
        
        # 结论：没有死循环。但为了保险，明确返回 intent_clear=False。
        return {
            "messages": [AIMessage(content=content)],
            "intent_clear": False
        }
