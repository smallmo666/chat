import asyncio
from src.workflow.state import AgentState
from src.workflow.nodes.analysis import analysis_node
from src.workflow.nodes.visualization import visualization_node

async def analysis_viz_node(state: AgentState, config: dict = None) -> dict:
    """
    后处理节点：并行执行数据分析和可视化生成。
    Renamed from post_process_node to match Planner's vocabulary "AnalysisViz".
    """
    print("DEBUG: Entering analysis_viz_node (Parallel Execution)")
    
    # 使用 asyncio.gather 并行运行
    # 由于 analysis_node 和 visualization_node 现在是原生 async 函数，
    # 我们可以直接并发调度它们，无需 ThreadPoolExecutor。
    
    try:
        # 并发执行
        analysis_result, viz_result = await asyncio.gather(
            analysis_node(state, config),
            visualization_node(state, config)
        )
    except Exception as e:
        print(f"Error in parallel execution: {e}")
        # 如果并发执行失败，尝试降级为顺序执行或部分返回
        # 这里为了简单，我们假设只要有一个成功就行，或者重新抛出
        # 但通常我们会想要捕获每个任务的异常。gather 默认是 fail-fast。
        # 使用 return_exceptions=True 可以避免一个失败导致全部失败
        results = await asyncio.gather(
            analysis_node(state, config),
            visualization_node(state, config),
            return_exceptions=True
        )
        analysis_result = results[0] if not isinstance(results[0], Exception) else {}
        viz_result = results[1] if not isinstance(results[1], Exception) else {}
        
    # Merge results
    return {
        "analysis": analysis_result.get("analysis"),
        "visualization": viz_result.get("visualization"),
        # 合并消息
        "messages": analysis_result.get("messages", []) + viz_result.get("messages", [])
    }
