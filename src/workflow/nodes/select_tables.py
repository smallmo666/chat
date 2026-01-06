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
        
    # 检索相关 Schema (异步 I/O) - 使用新的两阶段策略 (Candidate Search + LLM Rerank)
    async def _advanced_table_selection():
        # 1. 召回候选表 (Recall)
        def _get_candidates():
            searcher = get_schema_searcher(project_id)
            # 使用 search_candidate_tables 获取结构化候选列表
            # limit=10, internal vector search k=20, graph expansion -> potentially 30+ tables
            return searcher.search_candidate_tables(search_query, limit=10)
            
        candidates = await asyncio.to_thread(_get_candidates)
        
        if not candidates:
            return None
            
        print(f"DEBUG: Recall stage found {len(candidates)} candidate tables.")
        
        # 2. LLM Rerank / Selection
        # 构建候选表清单供 LLM 选择
        candidate_list_str = ""
        for i, t in enumerate(candidates):
            candidate_list_str += f"{i+1}. 表名: {t['table_name']}\n   注释: {t['comment']}\n"
            
        selection_prompt = ChatPromptTemplate.from_template(
            "你是一个数据库专家。请根据用户查询，从以下候选表中选出最相关的表。\n"
            "用户查询: {query}\n\n"
            "候选表列表:\n{candidates}\n\n"
            "选择原则:\n"
            "1. 包含用户查询所需字段的表。\n"
            "2. 如果涉及多表关联，必须选上连接表 (Join Table) 或中间表。\n"
            "3. 如果不确定，可以多选，但不要选明显无关的表。\n"
            "4. **务必进行连通性检查**：选出的表必须能通过外键连接起来。\n"
            "5. 如果存在多个表都能满足查询（例如 'sales_orders' 和 'purchase_orders'），且你不确定用户指的是哪一个，请返回状态 'AMBIGUOUS' 并提供选项。\n\n"
            "请先进行思考 (Chain of Thought)，分析查询需求和表之间的关系，然后再给出最终选择。\n"
            "输出 JSON 格式 (两种情况):\n"
            "情况 1: 意图清晰\n"
            "{{\n"
            "  \"status\": \"CLEAR\",\n"
            "  \"thought\": \"你的思考过程...\",\n"
            "  \"selected_tables\": [\"table1\", \"table2\"]\n"
            "}}\n\n"
            "情况 2: 意图模糊\n"
            "{{\n"
            "  \"status\": \"AMBIGUOUS\",\n"
            "  \"thought\": \"你的思考过程...\",\n"
            "  \"question\": \"请问您是指...?\",\n"
            "  \"options\": [\"选项A\", \"选项B\"]\n"
            "}}"
        )
        
        chain = selection_prompt | llm
        try:
            print("DEBUG: Invoking LLM for table selection with CoT...")
            result = await chain.ainvoke({"query": search_query, "candidates": candidate_list_str})
            content = result.content.strip()
            
            # 解析 JSON
            import json
            import re
            
            selected_names = []
            ambiguous_result = None
            
            # 尝试提取 JSON (支持包含 Markdown 代码块的情况)
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    json_data = json.loads(match.group(0))
                    print(f"DEBUG: Selection Thought: {json_data.get('thought', 'No thought provided')}")
                    
                    if json_data.get("status") == "AMBIGUOUS":
                        ambiguous_result = json_data
                    else:
                        selected_names = json_data.get("selected_tables", [])
                except:
                    pass
            
            # 处理歧义情况
            if ambiguous_result:
                print("DEBUG: Ambiguity detected in table selection.")
                return {
                    "status": "AMBIGUOUS",
                    "payload": ambiguous_result
                }

            if not selected_names:
                print("Warning: Failed to parse LLM selection, falling back to top 5 candidates.")
                selected_names = [t['table_name'] for t in candidates[:5]]
                
            print(f"DEBUG: LLM selected {len(selected_names)} tables: {selected_names}")

            # --- 自动连通性检查与补全 (Connectivity Check & Auto-Completion) ---
            # 目标：确保选中的表在图中是连通的。如果不连通，尝试寻找最短路径补充中间表。
            # 需要访问 searcher 的 adjacency_list
            searcher = get_schema_searcher(project_id)
            if hasattr(searcher, 'adjacency_list') and len(selected_names) > 1:
                adj = searcher.adjacency_list
                # 简单的 BFS 寻找连通分量
                def get_connected_components(nodes):
                    visited = set()
                    components = []
                    for node in nodes:
                        if node not in visited:
                            component = set()
                            queue = [node]
                            while queue:
                                curr = queue.pop(0)
                                if curr in visited: continue
                                visited.add(curr)
                                component.add(curr)
                                # 找当前节点在 selected_names 中的邻居（直接邻居）
                                # 注意：这里只看 selected_names 内部的连通性
                                # 但实际上我们需要看是否能在全图中连通
                                # 这里的逻辑是：如果 selected_names 在全图中不直接连通，我们需要找中间表
                                pass
                            components.append(component)
                    return components
                
                # 更简单的策略：对于每两个选中的表，检查是否可达。如果不可达，尝试补全。
                # 由于计算所有对的最短路径比较贵，我们采用“生成树”思路或简单贪心。
                # 这里实现一个简化的补全：如果集合不连通，尝试寻找 Candidates 中的中间表来连接它们。
                
                # 1. 构建子图：仅包含 selected_names 的节点
                # 检查连通性。如果不连通，尝试引入 candidates 中的其他表。
                
                final_selected = set(selected_names)
                
                # 检查是否所有表都在 adj 中
                valid_tables = [t for t in selected_names if t in adj]
                if len(valid_tables) > 1:
                    # 使用全图 BFS 寻找 valid_tables 之间的路径
                    # 简单起见，我们确保第一个表能到达其他所有表
                    root = valid_tables[0]
                    unreached = set(valid_tables[1:])
                    
                    # 寻找从 root 到 unreached 中每个节点的最短路径
                    # 限制路径长度，避免引入太多表
                    for target in unreached:
                        # BFS for shortest path
                        queue = [(root, [root])]
                        visited = {root}
                        found_path = None
                        
                        while queue:
                            curr, path = queue.pop(0)
                            if curr == target:
                                found_path = path
                                break
                            
                            if len(path) >= 4: # 限制最大跳数
                                continue
                                
                            for neighbor in adj.get(curr, []):
                                if neighbor not in visited:
                                    visited.add(neighbor)
                                    queue.append((neighbor, path + [neighbor]))
                        
                        if found_path:
                            # 将路径上的所有表加入 final_selected
                            for node in found_path:
                                if node not in final_selected:
                                    print(f"DEBUG: Auto-injecting intermediate table: {node}")
                                    final_selected.add(node)
                        else:
                            print(f"Warning: Could not find path between {root} and {target}")
                
                selected_names = list(final_selected)
            # -------------------------------------------------------------------
            
            # 3. 获取选中表的完整 Schema (使用列级精简)
            # 我们需要再次使用 Searcher 来获取精简版 Schema
            searcher = get_schema_searcher(project_id)
            # 调用新实现的 get_pruned_schema
            # 这里的 candidates 里的 full_info 虽然有全量信息，但我们想用 searcher 的逻辑来精简
            # 当然，也可以直接把 full_info 传给 searcher 处理，但 searcher 设计是查 metadata
            
            # 使用 get_pruned_schema 生成 Context
            final_schema_str = searcher.get_pruned_schema(selected_names, search_query)
            
            if not final_schema_str:
                 # Fallback
                 # 如果 Pruning 失败（例如 metadata 没加载），回退到 format_schema_str
                 print("Warning: Pruned schema generation failed, falling back to full schema.")
                 final_schema_dict = {}
                 candidate_map = {t['table_name']: t['full_info'] for t in candidates}
                 for name in selected_names:
                     if name in candidate_map:
                         final_schema_dict[name] = candidate_map[name]
                 return format_schema_str(final_schema_dict)

            return final_schema_str

            
        except Exception as e:
            print(f"DEBUG: LLM Selection failed: {e}")
            # Fallback to simple formatting of top candidates
            fallback_dict = {t['table_name']: t['full_info'] for t in candidates[:3]}
            return format_schema_str(fallback_dict)

    try:
        # 使用新的高级选择逻辑
        result_or_schema = await _advanced_table_selection()
        
        # 检查是否返回了歧义对象
        if isinstance(result_or_schema, dict) and result_or_schema.get("status") == "AMBIGUOUS":
            payload = result_or_schema["payload"]
            # 构造 ClarifyIntent 格式的输出
            # 直接返回 JSON 字符串，让前端 Card 组件渲染
            import json
            json_content = json.dumps(payload, ensure_ascii=False)
            
            return {
                "intent_clear": False,
                "messages": [AIMessage(content=json_content)],
                # 我们可能需要重置 plan 或者标记这一步为挂起，但 Supervisor 会处理 intent_clear=False
            }
            
        schema_info = result_or_schema
    except Exception as e:
        print(f"DEBUG: Advanced table selection failed: {e}")
        import traceback
        traceback.print_exc()
        schema_info = None
    
    # 检查失败情况
    if not schema_info:
        print("DEBUG: SelectTables failed to find tables. Aborting plan.")
        return {
            "relevant_schema": "",
            "messages": [AIMessage(content="抱歉，在数据库中未找到与您查询相关的表。请尝试更换关键词。")],
            "plan": [], # 清空计划以停止执行
            "current_step_index": 999 # 强制停止
        }

    # --- 优化：Schema 精简 (Async LLM) ---
    # 由于我们已经在上一步使用了 searcher.get_pruned_schema 进行了列级精简，
    # 这里原有的基于 LLM 的精简逻辑可以移除，或者作为兜底。
    # 鉴于 get_pruned_schema 已经非常高效且包含了 PK/FK，我们直接使用它的结果，不再调用 LLM 进行二次精简。
    
    # if len(schema_info) > 3000: ... (Removed)
    
    return {
        "relevant_schema": schema_info,
        "rewritten_query": search_query
    }
