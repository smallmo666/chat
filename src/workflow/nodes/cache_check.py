from langchain_core.messages import AIMessage
from src.workflow.state import AgentState
from src.domain.memory.semantic_cache import get_semantic_cache

def cache_check_node(state: AgentState, config: dict = None) -> dict:
    """
    语义缓存检查节点。
    在 Planner 之前运行，如果缓存命中，直接跳转到 ExecuteSQL。
    """
    print("DEBUG: Entering cache_check_node")
    
    # 获取用户最新查询
    messages = state["messages"]
    last_query = ""
    for msg in reversed(messages):
        if msg.type == "human":
            last_query = msg.content
            break
            
    if not last_query:
        return {"next": "Planner"} # 继续常规流程

    # 获取 Project ID
    project_id = config.get("configurable", {}).get("project_id") if config else None
    
    # 检查缓存
    cache = get_semantic_cache(project_id)
    cached_sql = cache.check(last_query)
    
    if cached_sql:
        print(f"DEBUG: Cache Hit! SQL: {cached_sql}")
        return {
            "sql": cached_sql,
            "next": "ExecuteSQL", # 跳过中间步骤
            # 我们需要伪造一个 Plan，否则 Supervisor 可能会困惑，或者我们直接告诉 Supervisor 下一步
            # 但为了 UI 显示，我们可以注入一个“虚拟计划”
            "plan": [
                {"node": "CacheCheck", "desc": "语义缓存命中", "status": "completed"},
                {"node": "ExecuteSQL", "desc": "执行缓存 SQL", "status": "wait"}
            ],
            "current_step_index": 1,
            "messages": [AIMessage(content="🔍 发现相似的历史查询，已从缓存加载 SQL。")]
        }
    
    # Cache Miss
    return {"next": "Planner"}
