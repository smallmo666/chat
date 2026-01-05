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
                    return {
                        "next": "GenerateDSL",
                        "current_step_index": gen_dsl_index + 1, # Next time supervisor runs, it will be after GenerateDSL
                        "plan_retry_count": plan_retry_count + 1,
                        "retry_count": 0, # Reset Inner Loop (SQL) retry count
                        "error": None # Clear error to allow fresh start
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
        
        # --- 3. Insight Mining Logic (主动洞察调度) ---
        # 触发条件: ExecuteSQL 之后 -> InsightMiner
        # 修正: 如果是从中断恢复 (inputs=None)，prev_node 可能是 None 或 ExecuteSQL (如果 Checkpoint 保存了状态变化)
        # 但如果是 approve 后恢复，LangGraph 实际上是刚刚运行完 ExecuteSQL (如果 interrupt_before=ExecuteSQL 且 resume 成功)
        # 或者如果是 interrupt_before，恢复时会直接执行 ExecuteSQL，然后才回到 Supervisor。
        # 此时 prev_node 应该是 ExecuteSQL。
        
        if prev_node == "ExecuteSQL":
            results_str = state.get("results")
            analysis_depth = state.get("analysis_depth", "simple")
            insights = state.get("insights")
            
            # 只有在 deep 模式且结果正常时才触发
            if (analysis_depth == "deep" 
                and results_str 
                and "Error" not in results_str 
                and "Empty" not in results_str
                and not insights):
                
                print("DEBUG: Supervisor - Routing to InsightMiner (Deep Analysis Mode)")
                # 这里我们不需要修改 plan，而是直接返回 next="InsightMiner"
                # 并且不增加 current_step_index
                return {
                    "next": "InsightMiner"
                }
        # ----------------------------------------------
        
        # --- 4. UI Artist Logic (生成式 UI 调度) ---
        # 触发条件: InsightMiner 之后 (或者 Visualization 之后，这里简化为 InsightMiner 之后)
        # 或者: 如果之前是通过 Supervisor 路由到 InsightMiner 的，那么从 InsightMiner 回来时，prev_node 仍然是 plan 中的节点吗？
        # 注意: LangGraph 的 state 传递是线性的。
        # 如果 Supervisor 返回了 {next: "InsightMiner"}，下一次 Supervisor 运行时，
        # state 中的 messages 会包含 InsightMiner 的输出，但 `plan` 和 `current_step_index` 没有变。
        # 此时我们需要知道 "上一步实际执行了什么"。
        # LangGraph 不会直接告诉我们上一步是谁，我们需要通过检查 State 变化来推断，或者依赖 plan 索引。
        
        # Hack: 我们检查 insights 字段是否存在且刚被填充。
        # 但更简单的方法是：
        # 如果当前 plan 步骤是 Visualization (尚未执行)，且我们有 insights (意味着刚从 InsightMiner 回来)，
        # 并且还没有生成 UI Component，则路由到 UIArtist。
        
        next_node_in_plan = plan[current_index]["node"] if current_index < len(plan) else None
        
        if next_node_in_plan == "Visualization":
            insights = state.get("insights")
            ui_component = state.get("ui_component")
            analysis_depth = state.get("analysis_depth", "simple")
            
            # 只有在 deep 模式，且有洞察，且尚未生成 UI 时
            if analysis_depth == "deep" and insights and not ui_component:
                 print("DEBUG: Supervisor - Routing to UIArtist (Deep Analysis Mode)")
                 return {
                     "next": "UIArtist"
                 }
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
