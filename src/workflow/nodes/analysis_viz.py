import asyncio
from src.workflow.state import AgentState
from src.workflow.nodes.analysis import analysis_node
from src.workflow.nodes.visualization import visualization_node

async def analysis_viz_node(state: AgentState, config: dict = None) -> dict:
    """
    并行执行数据分析和可视化节点。
    利用 asyncio 并发运行两个独立的 LLM 任务，减少总等待时间。
    """
    print("DEBUG: Entering analysis_viz_node (Parallel)")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="AnalysisViz", project_id=project_id)
    
    messages = state["messages"]
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # 在默认执行器（通常是 ThreadPoolExecutor）中运行同步的 LLM 节点
    future_analysis = loop.run_in_executor(None, analysis_node, state)
    future_viz = loop.run_in_executor(None, visualization_node, state)
    
    # 等待两个任务完成
    results = await asyncio.gather(future_analysis, future_viz, return_exceptions=True)
    
    analysis_result = results[0]
    viz_result = results[1]
    
    merged = {}
    
    # 处理 Analysis 结果
    if isinstance(analysis_result, Exception):
        print(f"Error in parallel analysis: {analysis_result}")
        merged["error"] = str(analysis_result) # 记录错误但不阻断流程
    elif isinstance(analysis_result, dict):
        merged.update(analysis_result)
        
    # 处理 Visualization 结果
    if isinstance(viz_result, Exception):
        print(f"Error in parallel visualization: {viz_result}")
    elif isinstance(viz_result, dict):
        # 注意：不要覆盖 messages，需要合并
        if "messages" in viz_result:
            viz_msgs = viz_result.pop("messages")
            # 将 viz 消息暂存，稍后合并
            merged["_viz_messages"] = viz_msgs
        merged.update(viz_result)
    
    # 合并 Messages
    # AgentState 使用 operator.add，所以我们返回一个列表即可
    final_messages = []
    if "messages" in merged:
        final_messages.extend(merged["messages"])
    if "_viz_messages" in merged:
        final_messages.extend(merged["_viz_messages"])
        del merged["_viz_messages"]
        
    if final_messages:
        merged["messages"] = final_messages
        
    return merged
