from src.workflow.state import AgentState
from src.domain.schema.search import get_schema_searcher
from src.core.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

def select_tables_node(state: AgentState, config: dict = None) -> dict:
    """
    表选择节点。
    根据用户的查询，从大规模数据库中检索出最相关的表结构。
    如果存在用户手动选择的表，优先使用。
    """
    print("DEBUG: Entering select_tables_node")
    
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="SelectTables", project_id=project_id)
    searcher = get_schema_searcher(project_id)

    manual_tables = state.get("manual_selected_tables", [])

    if manual_tables and len(manual_tables) > 0:
        # 用户显式选择了表。
        # 我们需要获取这些特定表的 Schema。
        
        # 限制手动表的数量以避免 Context 爆炸
        if len(manual_tables) > 20:
            manual_tables = manual_tables[:20]
            print(f"Warning: Too many manual tables selected. Truncating to top 20.")
            
        # 暂时从缓存手动构建 Schema 字符串以保持简单
        full_schema = searcher._get_schema()
        relevant_schema_info = []
        for table in manual_tables:
            if table in full_schema:
                # 处理旧版格式的 dict 和 list
                info = full_schema[table]
                columns = info if isinstance(info, list) else info.get("columns", [])
                
                col_strings = [f"{col['name']} ({col['type']})" + (f" - {col.get('comment')}" if col.get('comment') else "") for col in columns]
                table_comment = info.get("comment", "") if isinstance(info, dict) else ""
                
                header = f"表名: {table}"
                if table_comment:
                    header += f" ({table_comment})"
                
                relevant_schema_info.append(f"{header}\n列: {', '.join(col_strings)}")
        
        if not relevant_schema_info:
             # 如果未找到手动表（罕见），则回退
             schema_info = "User selected tables not found in schema."
        else:
             schema_info = "\n\n".join(relevant_schema_info)
             
        return {"relevant_schema": schema_info}

    # --- Multi-turn Context Handling ---
    messages = state["messages"]
    
    # 提取最近的 N 条对话历史（例如最近 3 轮），用于理解上下文
    # 过滤出 Human 和 AI 的消息
    recent_history = []
    history_depth = 6 # 3 rounds
    
    for msg in reversed(messages):
        if msg.type in ["human", "ai"]:
            recent_history.insert(0, msg)
        if len(recent_history) >= history_depth:
            break
            
    # 获取最新的用户查询
    last_human_msg = ""
    for msg in reversed(messages):
        if msg.type == "human":
            last_human_msg = msg.content
            break
            
    if not last_human_msg:
        return {"relevant_schema": "No user query found."}

    search_query = last_human_msg

    # 如果有历史对话，尝试重写查询以包含上下文（指代消解）
    if len(recent_history) > 1:
        try:
            llm = None # Will be initialized in node
            # 简单的历史格式化
            history_str = ""
            for msg in recent_history[:-1]: # Exclude current msg
                role = "User" if msg.type == "human" else "Assistant"
                history_str += f"{role}: {msg.content}\n"
            
            rewrite_prompt = ChatPromptTemplate.from_template(
                "你是一个搜索优化助手。你的任务是将用户的最新问题重写为一个独立的、包含完整上下文的数据库搜索查询。\n"
                "请解决指代问题（例如 '它' 指的是什么，'那些' 指的是什么），并补充缺失的限定条件。\n"
                "只要返回重写后的查询字符串，不要解释。\n\n"
                "对话历史:\n{history}\n"
                "最新问题: {current_query}\n\n"
                "重写后的查询:"
            )
            
            chain = rewrite_prompt | llm
            if config:
                result = chain.invoke({"history": history_str, "current_query": last_human_msg}, config=config)
            else:
                result = chain.invoke({"history": history_str, "current_query": last_human_msg})
                
            rewritten_query = result.content.strip()
            print(f"DEBUG: Rewritten Query: '{last_human_msg}' -> '{rewritten_query}'")
            search_query = rewritten_query
            
        except Exception as e:
            print(f"Query rewrite failed: {e}")
            # Fallback to original query
            search_query = last_human_msg

    # 检索相关表 Schema (使用重写后的查询)
    schema_info = searcher.search_relevant_tables(search_query)
    
    # Check for failure
    if not schema_info or "No relevant tables found" in schema_info or "No schema available" in schema_info:
        print("DEBUG: SelectTables failed to find tables. Aborting plan.")
        return {
            "relevant_schema": "",
            "messages": [AIMessage(content="抱歉，在数据库中未找到与您查询相关的表。请尝试更换关键词或确认数据库结构。")],
            "plan": [], # Clear plan to stop execution immediately
            "current_step_index": 999 # Force stop
        }

    # --- Optimization: Schema Pruning ---
    # 如果 Schema 过大（例如超过 3000 字符），使用 LLM 进行精简，只保留相关列
    if len(schema_info) > 3000:
        print(f"DEBUG: Schema too large ({len(schema_info)} chars). Pruning...")
        try:
            llm = None # Will be initialized in node
            prune_prompt = ChatPromptTemplate.from_template(
                "你是一个数据库 Schema 精简助手。\n"
                "用户查询: {query}\n"
                "原始 Schema 信息:\n{schema}\n\n"
                "任务：请保留与用户查询最相关的表和列，去除无关的表和列。\n"
                "保留表之间的关联键（主键/外键）以确保能正确连接。\n"
                "输出格式保持原样（表名... 列...）。"
            )
            chain = prune_prompt | llm
            result = chain.invoke({"query": search_query, "schema": schema_info})
            pruned_schema = result.content.strip()
            print(f"DEBUG: Pruned schema size: {len(pruned_schema)} chars")
            schema_info = pruned_schema
        except Exception as e:
            print(f"Schema pruning failed: {e}")
            # Fallback to original
    # ------------------------------------

    return {
        "relevant_schema": schema_info,
        "rewritten_query": search_query # 将重写后的查询传递给下游节点 (如 GenDSL)
    }
