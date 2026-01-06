from src.workflow.state import AgentState

def supervisor_node(state: AgentState, config: dict = None) -> dict:
    """
    Supervisor Node.
    Decides the next node to execute based on the plan and current state.
    Routes to InsightMiner and UIArtist if applicable.
    """
    print("DEBUG: Entering supervisor_node")
    try:
        # --- 1. Intent Check ---
        # 如果 ClarifyIntent 标记意图不清晰，立即停止流程，等待用户回复
        intent_clear = state.get("intent_clear", True) # 默认为 True
        if intent_clear is False:
             print("DEBUG: Supervisor - Intent NOT clear. Stopping execution.")
             return {"next": "FINISH"}
        # -----------------------

        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        
        print(f"DEBUG: Supervisor - Plan len: {len(plan)}, Current Index: {current_index}")

        # --- 2. Retry Logic (Outer Loop: Plan Regeneration) ---
        error = state.get("error")
        if error:
            # Check Plan Retry Count (Global Retry)
            plan_retry_count = state.get("plan_retry_count", 0)
            print(f"DEBUG: Supervisor - Detected error: {error}. Plan retry count: {plan_retry_count}")
            
            # Max 2 global retries (rewind to GenerateDSL)
            if plan_retry_count < 2:
                # Find the index of GenerateDSL to rewind
                gen_dsl_index = -1
                for i, step in enumerate(plan):
                    if step["node"] == "GenerateDSL":
                        gen_dsl_index = i
                        break
                
                if gen_dsl_index != -1:
                    print(f"DEBUG: Supervisor - Rewinding to GenerateDSL (index {gen_dsl_index}) for plan retry.")
                    # 清除可能导致死循环的状态 (如 dsl, sql)
                    # 我们希望 GenerateDSL 重新生成，而不是使用旧的
                    return {
                        "next": "GenerateDSL",
                        "current_step_index": gen_dsl_index + 1, # Next time supervisor runs, it will be after GenerateDSL
                        "plan_retry_count": plan_retry_count + 1,
                        "retry_count": 0, # Reset Inner Loop (SQL) retry count
                        "error": None, # Clear error to allow fresh start
                        "dsl": None, # Force regenerate DSL
                        "sql": None
                    }
                else:
                    print("DEBUG: Supervisor - GenerateDSL not found in plan, cannot retry.")
            else:
                print("DEBUG: Supervisor - Max plan retries reached. Proceeding with error.")
                # 即使重试次数耗尽，我们也不应该继续执行错误的计划（比如去 Visualization）
                # 应该直接结束，并确保错误信息被保留，以便前端显示
                return {"next": "FINISH"}
        # -------------------
        
        # 获取上一步执行的节点 (注意 current_index 指向的是 *下一步* 要执行的，所以上一步是 current_index - 1)
        prev_node = plan[current_index - 1]["node"] if current_index > 0 else None
        
        # --- 3. Intelligent Analysis & Visualization Logic ---
        # 触发条件: ExecuteSQL 之后
        # 1. 如果 deep analysis -> PythonAnalysis
        # 2. 如果 normal/deep 且有数据 -> VisualizationAdvisor (为 SQL 数据生成图表建议)
        
        if prev_node == "ExecuteSQL":
            results_str = state.get("results")
            analysis_depth = state.get("analysis_depth", "simple")
            python_analysis_result = state.get("analysis")
            viz_config = state.get("visualization")
            
            has_data = results_str and "Error" not in results_str and "Empty" not in results_str
            
            # 优先路由到 PythonAnalysis (如果需要深度分析且未执行过)
            if (analysis_depth == "deep" and has_data and not python_analysis_result):
                print("DEBUG: Supervisor - Routing to PythonAnalysis (Deep Analysis Mode)")
                return {"next": "PythonAnalysis"}
                
            # 其次路由到 VisualizationAdvisor (如果尚未生成配置且有数据)
            # 注意：即使是 deep 模式，PythonAnalysis 执行完后也会回到这里（如果它没有直接跳过）
            # 但我们需要一种机制让 PythonAnalysis 执行完后能继续。
            # 当前逻辑：PythonAnalysis 执行完后，next_node_in_plan 是 Visualization。
            # 所以我们需要在 PythonAnalysis 之后也触发 VisualizationAdvisor？
            # 不，VisualizationAdvisor 是为了给 UIArtist 提供建议。
            # 如果 plan 中包含 Visualization，我们应该在 UIArtist 之前运行 Advisor。
            
            # 让我们简化：
            # 只要 ExecuteSQL 成功，且还没有 viz_config，就去 Advisor。
            if has_data and not viz_config:
                 print("DEBUG: Supervisor - Routing to VisualizationAdvisor")
                 # 注意：这里我们插入一个临时步骤，不增加 current_step_index
                 # 这样 Advisor 执行完后，Supervisor 会再次运行，然后继续正常的 plan (或 deep logic)
                 return {"next": "VisualizationAdvisor"}

        # ----------------------------------------------
        
        # --- 4. UI Artist Logic (生成式 UI 调度) ---
        # 触发条件: PythonAnalysis 之后 (Deep) 或 VisualizationAdvisor 之后 (Normal)
        
        next_node_in_plan = plan[current_index]["node"] if current_index < len(plan) else None
        
        if next_node_in_plan == "Visualization":
            # 如果是 Deep 模式，确保 PythonAnalysis 已完成
            analysis_depth = state.get("analysis_depth", "simple")
            python_analysis_result = state.get("analysis")
            ui_component = state.get("ui_component")
            
            # Deep Mode Check
            if analysis_depth == "deep" and not python_analysis_result:
                 # 这通常由上面的逻辑处理，但作为双重检查
                 pass 
            
            # 只有在尚未生成 UI 时才路由到 UIArtist
            # 注意：如果 plan 里本身就有 Visualization 节点，supervisor 会自然流转到它。
            # 但我们在 graph.py 里可能把 Visualization 节点映射到了 ui_artist_node。
            # 这里我们只是做特殊的"插队"逻辑。
            # 如果 next_node 就是 Visualization，我们不需要做任何特殊路由，直接让它走下面的 return {"next": next_node} 即可。
            # 除非我们需要在 Visualization 之前强制插入 UIArtist (如果它们是同一个节点，则无需操作)
            
            # 关键点：我们需要区分 "Visualization" (Plan Step) 和 "UIArtist" (Node Name).
            # 假设 Plan 中的 Visualization 对应的是 ui_artist_node。
            # 那么我们不需要在这里做任何事，除了 Deep Mode 的特殊插队 (PythonAnalysis)。
            
            pass 
        # ----------------------------------------------

        # 如果没有计划或已完成所有步骤，则结束
        if not plan or current_index >= len(plan):
            print("DEBUG: Supervisor - Plan finished or empty -> FINISH")
            return {"next": "FINISH"}
        
        # 获取下一步节点名称
        next_node = plan[current_index]["node"]
        print(f"DEBUG: Supervisor - Next node: {next_node}")
        
        return {
            "next": next_node,
            "current_step_index": current_index + 1
        }
    except Exception as e:
        print(f"ERROR in supervisor_node: {e}")
        import traceback
        traceback.print_exc()
        return {"next": "FINISH"} # 故障安全
