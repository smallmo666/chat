from src.workflow.state import AgentState

def supervisor_node(state: AgentState, config: dict = None) -> dict:
    """
    Supervisor Node.
    Decides the next node to execute based on the plan and current state.
    """
    print("DEBUG: Entering supervisor_node")
    try:
        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        
        print(f"DEBUG: Supervisor - Plan len: {len(plan)}, Current Index: {current_index}")

        # --- Retry Logic (Outer Loop: Plan Regeneration) ---
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
        # -------------------
        
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
