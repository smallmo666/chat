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
    # 注意：analysis_node 和 visualization_node 目前是同步函数，
    # 如果它们内部没有耗时 I/O (除了 LLM 调用)，我们需要确保它们能在线程池中运行，
    # 或者将它们改为 async 函数。
    # 目前 LLM 调用通常是同步阻塞的 (langchain default)，除非使用 ainvoke。
    # 为了真正的并行，我们需要它们内部使用 async LLM calls。
    
    # 既然我们无法轻易修改 node 签名为 async (LangGraph 支持，但我们要改 node 实现)，
    # 我们这里先简单地顺序调用，但逻辑上合并了。
    # 为了演示并行，我们使用 run_in_executor 或假设它们是 async 的。
    
    # 实际上，LangChain 的 invoke 是同步的。要并行，我们需要使用 ainvoke。
    # 让我们修改 analysis_node 和 visualization_node 为 async? 
    # 或者在这里做些 hack。
    
    # 简单方案：顺序执行，但作为一个原子步骤，减少了 Supervisor 的调度开销。
    # 优化方案：重构 analysis 和 viz 为 async。
    
    # 这里我们采用“逻辑并行”：
    # 1. 启动 Analysis 任务
    # 2. 启动 Viz 任务
    # 3. 等待两者完成
    
    # 由于原始节点函数是同步的，我们在这里直接调用它们。
    # 如果想要并行，我们可以在这里使用 ThreadPoolExecutor。
    
    import concurrent.futures
    
    loop = asyncio.get_running_loop()
    
    with concurrent.futures.ThreadPoolExecutor() as pool:
        # Submit tasks
        future_analysis = loop.run_in_executor(pool, analysis_node, state, config)
        future_viz = loop.run_in_executor(pool, visualization_node, state, config)
        
        # Wait for results
        analysis_result = await future_analysis
        viz_result = await future_viz
        
    # Merge results
    return {
        "analysis": analysis_result.get("analysis"),
        "visualization": viz_result.get("visualization"),
        # 合并消息
        "messages": analysis_result.get("messages", []) + viz_result.get("messages", [])
    }
