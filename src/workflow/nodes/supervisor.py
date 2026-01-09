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
        if clarify_pending or (clarify_payload and not state.get("clarify_answer")):
            print("DEBUG: Supervisor - Clarify pending detected globally. Halting for user selection.")
            return {"next": "FINISH", "clarify_pending": True}
        if intent_clear is False:
            # Check if user has already provided an answer (this overrides intent_clear=False)
            if state.get("clarify_answer"):
                print("DEBUG: Supervisor - Clarify answer present, overriding intent_clear=False and proceeding.")
                # If plan is empty (which happens if clarification occurred before SelectTables/GenerateDSL),
                # we must route to the next logical step, usually SelectTables or Planner.
                # Since clarification usually happens when intent is ambiguous before table selection, 
                # and based on user log, the next expected node is SelectTables.
                if not plan:
                    print("DEBUG: Supervisor - No plan after clarification, routing to SelectTables.")
                    return {"next": "SelectTables"}
                
                # If plan exists, we fall through to let the plan continue execution.
                pass 
            # 若刚执行 ClarifyIntent 或已有澄清挂起，则不再路由 ClarifyIntent，挂起等待选择或自动兜底
            elif (last_executed == "ClarifyIntent") or clarify_payload or clarify_pending:
                # Calculate rewind index to ensure we retry the current step after clarification
                # If we are at step X (current_index), and we halt, we want to resume at step X (or the step that triggered clarify)
                # Usually, ClarifyIntent is inserted dynamically or we are just pausing before executing the plan step.
                # So we should keep current_index as is, or ensure we don't increment it prematurely.
                # However, the return value of supervisor usually sets state update.
                # If we return "next": "FINISH", we are not updating current_step_index in the state (unless we explicitly return it).
                # But to be safe and explicit:
                rewind_index = current_index 
                
                # 设置挂起
                if not clarify_pending:
                    print("DEBUG: Supervisor - Clarify pending set. Halting plan for user selection.")
                    return {
                        "next": "FINISH",
                        "clarify_pending": True,
                        "clarify_retry_count": clarify_retry,
                        "current_step_index": rewind_index # Explicitly keep index
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
            else:
                # 首次进入 ClarifyIntent
                if prev_node not in {"ClarifyIntent", "SelectTables"} and last_executed not in {"ClarifyIntent", "SelectTables"}:
                    print("DEBUG: Supervisor - Intent NOT clear. Routing to ClarifyIntent.")
                    return {"next": "ClarifyIntent"}
                print("DEBUG: Supervisor - Intent NOT clear after clarification/select. Finishing.")
                return {"next": "FINISH"}
        # -----------------------

        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        
        # --- Post-Clarification Routing ---
        # 如果刚刚完成了澄清（有答案且意图清晰），且计划已结束或为空，说明之前的计划只是为了澄清。
        # 现在需要重新规划真正的执行路径。
        if state.get("clarify_answer") and intent_clear and (not plan or current_index >= len(plan)):
            print("DEBUG: Supervisor - Clarification complete. Routing to Planner for re-planning.")
            return {
                "next": "Planner",
                "current_step_index": 0, # 重置索引
                "plan": [], # 清空旧计划，强制 Planner 生成新计划
                # 关键：保留 clarify_answer，让 Planner 能看到用户的澄清选择，从而生成正确的计划
                # Planner 会在生成计划后负责清理这个字段，或者通过 last_executed_node 判断
                # "clarify_answer": None,  <-- 不要在这里清除！
            }
        
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
            # Special case: If intent is clear but no plan exists (e.g. after clarification),
            # we should start the flow, typically with SelectTables (or Planner).
            # Assuming SelectTables is the first step of a standard flow.
            if not plan and intent_clear:
                 print("DEBUG: Supervisor - Intent clear but no plan. Routing to SelectTables.")
                 return {"next": "SelectTables"}
            
            print("DEBUG: Supervisor - Plan finished or empty -> FINISH")
            return {"next": "FINISH"}
        
        # 获取下一步节点名称
        next_node = plan[current_index]["node"]
        print(f"DEBUG: Supervisor - Next node: {next_node}")
        
        # --- GenerateDSL 前置检查 ---
        if next_node == "GenerateDSL" and not state.get("allowed_schema"):
            print(f"DEBUG: Supervisor - Pre-GenerateDSL check: selected_tables={state.get('selected_tables')}, allowed_schema={state.get('allowed_schema')}")
            sel = state.get("selected_tables") or []
            if sel:
                print(f"DEBUG: Supervisor - Building allowed_schema from selected_tables: {sel}")
                return {
                    "next": "GenerateDSL",
                    "current_step_index": current_index + 1,
                    "allowed_schema": {t: [] for t in sel}
                }
            # 如果上一步已经是 SchemaGuard，说明尝试获取 Schema 失败，不能死循环
            if last_executed == "SchemaGuard":
                print("DEBUG: Supervisor - SchemaGuard failed, attempting fallback allowed_schema.")
                rel = state.get("relevant_schema", "") or ""
                import re as _re
                tables = []
                for line in rel.split("\n"):
                    if line.startswith("表名:"):
                        m = _re.match(r"表名:\s*([A-Za-z0-9_.]+)", line)
                        if m:
                            tables.append(m.group(1))
                if tables:
                    print(f"DEBUG: Supervisor - Fallback allowed_schema using tables: {tables}")
                    return {
                        "next": "GenerateDSL",
                        "current_step_index": current_index + 1,
                        "allowed_schema": {t: [] for t in tables}
                    }
                print("DEBUG: Supervisor - SchemaGuard failed to produce allowed_schema. Halting to prevent loop.")
                return {
                     "next": "FINISH",
                     "error": "无法确定查询涉及的数据表 (SchemaGuard Failed)。请尝试提供更详细的表名信息。"
                }
            # 如果上一步是 SelectTables 且它也失败了（没有 allowed_schema），通常 SelectTables 会处理 ambiguity。
            # 但如果 SelectTables 认为意图清晰却没选出表（极少见），或者直接被跳过，我们需要防御。
            
            print("DEBUG: Supervisor - No allowed_schema before GenerateDSL, routing to SchemaGuard.")
            # 关键：不要增加 current_step_index，这样 SchemaGuard 执行完后，Supervisor 会再次检查
            # 由于 SchemaGuard 执行后 last_executed 变为 SchemaGuard，如果它成功产出 schema，
            # 下次循环将进入 else 分支正常执行 GenerateDSL。
            # 如果它失败，将触发上面的 Loop Prevention。
            return {
                "next": "SchemaGuard",
                # current_step_index 保持不变，意味着 SchemaGuard 是“插入”的步骤
                # 但我们需要小心，如果 SchemaGuard 不在 plan 里，我们需要它执行完后回到这里。
                # 如果我们不增加 index，supervisor 下次还是看 index=3 (GenerateDSL)。
                # 这样是对的。
                "current_step_index": current_index 
            }
        # ExecuteSQL 前置保护：无 SQL 不进入执行链
        if next_node == "ExecuteSQL" and not state.get("sql"):
            print("DEBUG: Supervisor - No SQL present, preventing ExecuteSQL. Routing back to DSLtoSQL")
            return {
                "next": "DSLtoSQL",
                "current_step_index": current_index  # 不推进索引，回到编译步骤
            }

        return {
            "next": next_node,
            "current_step_index": current_index + 1
        }
    except Exception as e:
        print(f"ERROR in supervisor_node: {e}")
        import traceback
        traceback.print_exc()
        return {"next": "FINISH"} # 故障安全
