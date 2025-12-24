from src.state.state import AgentState

def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor Node (Dispatcher).
    Reads the 'plan' from state and 'current_step_index' to determine the next node.
    """
    print("DEBUG: Entering supervisor_node")
    try:
        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        
        print(f"DEBUG: Supervisor - Plan len: {len(plan)}, Current Index: {current_index}")
        
        # If no plan or finished all steps, END
        if not plan or current_index >= len(plan):
            print("DEBUG: Supervisor - Plan finished or empty -> FINISH")
            return {"next": "FINISH"}
        
        # Get next step node name
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
        return {"next": "FINISH"} # Fail safe
