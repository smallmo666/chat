import asyncio
from langchain_core.messages import AIMessage
from src.workflow.state import AgentState
from src.domain.memory.semantic_cache import get_semantic_cache

async def cache_check_node(state: AgentState, config: dict = None) -> dict:
    """
    语义缓存检查节点 (Async)。
    在 Planner 之前运行，如果缓存命中，直接跳转到 ExecuteSQL。
    """
    print("DEBUG: Entering cache_check_node (Async)")
    
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
    
    # 检查缓存 (异步 I/O)
    def _check_cache():
        cache = get_semantic_cache(project_id)
        return cache.check(last_query)

    try:
        cached_sql = await asyncio.to_thread(_check_cache)
    except Exception as e:
        print(f"DEBUG: Cache check failed: {e}")
        cached_sql = None
    
    if cached_sql:
        print(f"DEBUG: Cache Hit! SQL: {cached_sql}")
        return {
            "sql": cached_sql,
            "next": "ExecuteSQL", # 跳过中间步骤
            # 构建缓存命中的执行计划，确保包含分析和可视化步骤
            # 注意: AnalysisViz 已废弃，替换为 Visualization
            "plan": [
                {"node": "CacheCheck", "desc": "语义缓存命中", "status": "completed"},
                {"node": "ExecuteSQL", "desc": "执行缓存 SQL", "status": "wait"},
                {"node": "Visualization", "desc": "结果分析与可视化", "status": "wait"}
            ],
            # 设置 current_step_index 指向 Plan 中的第三个节点 (Visualization)
            # 因为 ExecuteSQL 会由 Conditional Edge 直接触发，且 ExecuteSQL 不会推进 index
            # 所以当 ExecuteSQL 完成后回到 Supervisor 时，Supervisor 应该看到 index=2
            "current_step_index": 2, 
            "messages": [AIMessage(content="🔍 发现相似的历史查询，已从缓存加载 SQL。")]
        }
    
    # Cache Miss
    return {"next": "Planner"}
