from src.workflow.state import AgentState

def supervisor_node(state: AgentState, config: dict = None) -> dict:
    """
    Supervisor Node.
    Decides the next node to execute based on the plan and current state.
    """
    project_id = config.get("configurable", {}).get("project_id") if config else None
    llm = get_llm(node_name="Supervisor", project_id=project_id)
    
    print("DEBUG: Entering supervisor_node")
    try:
        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        
        print(f"DEBUG: Supervisor - Plan len: {len(plan)}, Current Index: {current_index}")

        # --- Retry Logic ---
        error = state.get("error")
        if error:
            retry_count = state.get("retry_count", 0)
            print(f"DEBUG: Supervisor - Detected error: {error}. Retry count: {retry_count}")
            
            if retry_count < 3:
                # Find the index of GenerateDSL to rewind
                gen_dsl_index = -1
                for i, step in enumerate(plan):
                    if step["node"] == "GenerateDSL":
                        gen_dsl_index = i
                        break
                
                if gen_dsl_index != -1:
                    print(f"DEBUG: Supervisor - Rewinding to GenerateDSL (index {gen_dsl_index}) for retry.")
                    return {
                        "next": "GenerateDSL",
                        "current_step_index": gen_dsl_index + 1, # Next time supervisor runs, it will be after GenerateDSL
                        "retry_count": retry_count + 1
                    }
                else:
                    print("DEBUG: Supervisor - GenerateDSL not found in plan, cannot retry.")
            else:
                print("DEBUG: Supervisor - Max retries reached. Proceeding with error.")
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
