from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.state.state import AgentState
from src.utils.llm import get_llm
from src.utils.memory import get_memory

llm = get_llm()

def clarify_intent_node(state: AgentState, config: dict) -> dict:
    """
    意图澄清节点。
    使用 LLM 分析用户意图，如果意图不清晰，则生成澄清问题。
    集成长期记忆：在分析意图时参考用户的历史偏好。
    """
    
    # 获取最后一条消息
    last_msg = state["messages"][-1].content
    
    # 获取用户 ID (从 config 中获取 thread_id 作为 user_id，或者使用默认值)
    user_id = config.get("configurable", {}).get("thread_id", "default_user")
    
    # 检索长期记忆
    memories = []
    try:
        memory_client = get_memory()
        mem_results = memory_client.search(user_id=user_id, query=last_msg, limit=3)
        memories = [m["memory"] for m in mem_results] if mem_results else []
    except Exception as e:
        # print(f"检索记忆失败: {e}")
        pass

    memory_context = "\n".join([f"- {m}" for m in memories]) if memories else "无历史记录"
    
    system_prompt = (
        "你是一个 Text2SQL 的意图分析专家。\n"
        "你的任务是判断用户的输入是否包含足够的信息来构建 SQL 查询（针对 users 表：id, name, age, joined_year）。\n\n"
        "用户的相关历史记忆/偏好：\n"
        "{memory_context}\n\n"
        "规则：\n"
        "1. 如果意图清晰，且与查询数据相关，请只输出 'CLEAR'。\n"
        "2. 如果意图不清晰，或者缺少关键信息（例如用户只说了'查询'但没说查什么），请输出一个简短的澄清问题，询问用户具体想查询什么。\n"
        "注意：如果用户的模糊查询可以通过历史记忆补全（例如用户以前总查 2023 年的数据），你可以认为意图清晰，不需要澄清。"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ]).partial(memory_context=memory_context)
    
    chain = prompt | llm
    result = chain.invoke({"query": last_msg}, config=config)
    content = result.content.strip()
    
    if content == "CLEAR":
        return {"intent_clear": True}
    else:
        # 如果不是 CLEAR，说明是澄清问题
        # 我们将问题返回给用户，并标记意图未澄清
        return {
            "messages": [AIMessage(content=content)],
            "intent_clear": False
        }
