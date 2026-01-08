from src.workflow.state import AgentState
from src.workflow.utils.snapshot import save_snapshot, gen_snapshot_token

def supervisor_node(state: AgentState, config: dict = None) -> dict:
    """
    Supervisor Node.
    Decides the next node to execute based on the plan and current state.
    Routes to InsightMiner and UIArtist if applicable.
    """
    print("DEBUG: Entering supervisor_node")
    try:
        # --- 1. Intent Check ---
        intent_clear = state.get("intent_clear", True)
        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        prev_node = plan[current_index - 1]["node"] if current_index > 0 else None
        last_executed = state.get("last_executed_node")
        clarify_payload = state.get("clarify")
        clarify_pending = state.get("clarify_pending", False)
        clarify_retry = int(state.get("clarify_retry_count", 0) or 0)
        # Interrupt handling
        interrupt_pending = bool(state.get("interrupt_pending"))
        if interrupt_pending:
            print("DEBUG: Supervisor - Interrupt detected. Saving snapshot and finishing.")
            token = state.get("snapshot_token")
            if not token:
                token = gen_snapshot_token(state)
            configurable = config.get("configurable", {}) if config else {}
            project_id = configurable.get("project_id")
            thread_id = configurable.get("thread_id", "default_thread")
            try:
                save_snapshot(state, project_id, thread_id, token)
            except Exception as _:
                pass
            return {
                "next": "FINISH",
                "snapshot_token": token,
                "interrupt_pending": True
            }
        if intent_clear is False:
            # 若刚执行 ClarifyIntent 或已有澄清挂起，则不再路由 ClarifyIntent，挂起等待选择或自动兜底
            if (last_executed == "ClarifyIntent") or clarify_payload or clarify_pending:
                # 设置挂起
                if not clarify_pending:
                    print("DEBUG: Supervisor - Clarify pending set. Halting plan for user selection.")
                    return {
                        "next": "FINISH",
                        "clarify_pending": True,
                        "clarify_retry_count": clarify_retry
                    }
                # 自动兜底：超过重试上限时进行自动选择
                if clarify_pending and clarify_retry >= 1:
                    def _auto_select(opts: list[str]) -> str | None:
                        if not opts:
                            return None
                        # 选择更可能代表“销售额/金额”的字段
                        # 优先包含 amount/total/value/sum；避免 unit/price_per/unit_value
                        def score(opt: str) -> float:
                            s = 0.0
                            low = opt.lower()
                            if any(k in low for k in ["amount","total","value","sum","revenue","sales"]):
                                s += 1.0
                            if "transaction" in low:
                                s += 0.5
                            if any(k in low for k in ["unit","per_unit","unit_value","unitprice"]):
                                s -= 0.8
                            # 数值列的指示很难在此处获取类型；仅用词汇启发
                            return s
                        best = sorted(opts, key=score, reverse=True)[0]
                        return best
                    opts = []
                    try:
                        opts = clarify_payload.get("options", [])
                    except Exception:
                        opts = []
                    chosen = _auto_select(opts)
                    print(f"DEBUG: Supervisor - Auto-selected clarify option: {chosen}")
                    return {
                        "next": "FINISH",
                        "clarify_pending": False,
                        "clarify_answer": chosen,
                        "clarify_retry_count": clarify_retry + 1
                    }
                # 已挂起但未达到重试→保持挂起状态，避免循环
                print("DEBUG: Supervisor - Intent NOT clear but pending; finishing to await input.")
                return {"next": "FINISH"}
            # 首次进入 ClarifyIntent
            if prev_node not in {"ClarifyIntent", "SelectTables"} and last_executed not in {"ClarifyIntent", "SelectTables"}:
                print("DEBUG: Supervisor - Intent NOT clear. Routing to ClarifyIntent.")
                return {"next": "ClarifyIntent"}
            print("DEBUG: Supervisor - Intent NOT clear after clarification/select. Finishing.")
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
            
            # 增强的空数据检测逻辑
            # ExecuteSQL 在无数据时返回 "[]"
            is_empty_json = results_str and results_str.strip() == "[]"
            has_data = results_str and "Error" not in results_str and "Empty" not in results_str and not is_empty_json
            
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
