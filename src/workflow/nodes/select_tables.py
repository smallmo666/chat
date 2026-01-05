from src.workflow.state import AgentState
from src.domain.schema.search import get_schema_searcher
from src.core.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from src.workflow.utils.schema_format import format_schema_str
import asyncio

async def select_tables_node(state: AgentState, config: dict = None) -> dict:
    """
    表选择节点 (Async)。
    根据用户的查询，从大规模数据库中检索出最相关的表结构。
    如果存在用户手动选择的表，优先使用。
    """
    print("DEBUG: Entering select_tables_node (Async)")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    
    # 延迟初始化 LLM
    llm = get_llm(node_name="SelectTables", project_id=project_id)
    # 移除主线程中的 get_schema_searcher 调用，移入 worker thread 以避免初始化阻塞
    # searcher = get_schema_searcher(project_id) 

    manual_tables = state.get("manual_selected_tables", [])

    if manual_tables and len(manual_tables) > 0:
        # 处理手动选择的表
        if len(manual_tables) > 20:
            manual_tables = manual_tables[:20]
            print(f"Warning: Too many manual tables selected. Truncating to top 20.")
            
        # 获取手动表的 Schema (异步 I/O)
        def _get_manual_schema():
            # 在 worker thread 中获取 searcher 实例，防止初始化阻塞
            searcher = get_schema_searcher(project_id)
            full_schema = searcher._get_schema()
            relevant_schema_dict = {}
            for table in manual_tables:
                if table in full_schema:
                    relevant_schema_dict[table] = full_schema[table]
            return relevant_schema_dict

        relevant_schema_dict = await asyncio.to_thread(_get_manual_schema)
        
        if not relevant_schema_dict:
             schema_info = "User selected tables not found in schema."
        else:
             # 使用统一的格式化器
             schema_info = format_schema_str(relevant_schema_dict)
             
        return {"relevant_schema": schema_info}

    # --- 多轮对话上下文处理 ---
    messages = state["messages"]
    
    # 获取最新的用户查询
    last_human_msg = ""
    for msg in reversed(messages):
        if msg.type == "human":
            last_human_msg = msg.content
            break
            
    if not last_human_msg:
        # Fallback: Check if there's a rewritten query even if no human message found in current slice
        rewritten_query = state.get("rewritten_query")
        if rewritten_query:
            last_human_msg = rewritten_query
        else:
            return {"relevant_schema": "No user query found."}

    # 使用已有的重写查询（如果有）
    rewritten_query = state.get("rewritten_query")
    if rewritten_query:
        search_query = rewritten_query
        print(f"DEBUG: SelectTables using existing rewritten query: '{search_query}'")
    else:
        search_query = last_human_msg
        
    # 检索相关 Schema (异步 I/O)
    def _search_schema():
        # 在 worker thread 中获取 searcher 实例，防止初始化阻塞
        searcher = get_schema_searcher(project_id)
        return searcher.search_relevant_tables(search_query)

    try:
        schema_info = await asyncio.to_thread(_search_schema)
    except Exception as e:
        print(f"DEBUG: Schema search failed: {e}")
        schema_info = None
    
    # 检查失败情况
    if not schema_info or "No relevant tables found" in schema_info or "No schema available" in schema_info:
        print("DEBUG: SelectTables failed to find tables. Aborting plan.")
        return {
            "relevant_schema": "",
            "messages": [AIMessage(content="抱歉，在数据库中未找到与您查询相关的表。请尝试更换关键词。")],
            "plan": [], # 清空计划以停止执行
            "current_step_index": 999 # 强制停止
        }

    # --- 优化：Schema 精简 (Async LLM) ---
    if len(schema_info) > 3000:
        print(f"DEBUG: Schema too large ({len(schema_info)} chars). Pruning...")
        try:
            prune_prompt = ChatPromptTemplate.from_template(
                "你是一个数据库 Schema 精简助手。\n"
                "用户查询: {query}\n"
                "原始 Schema:\n{schema}\n\n"
                "任务：请保留与用户查询最相关的表和列，去除无关的表和列。\n"
                "保留主键/外键以确保可以正确进行表连接。\n"
                "输出格式应保持一致 (Table... Columns...)。"
            )
            chain = prune_prompt | llm
            # 异步调用 LLM
            result = await chain.ainvoke({"query": search_query, "schema": schema_info})
            pruned_schema = result.content.strip()
            print(f"DEBUG: Pruned schema size: {len(pruned_schema)} chars")
            schema_info = pruned_schema
        except Exception as e:
            print(f"Schema pruning failed: {e}")

    return {
        "relevant_schema": schema_info,
        "rewritten_query": search_query
    }
