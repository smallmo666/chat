from src.state.state import AgentState

def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor Node (Dispatcher).
    Reads the 'plan' from state and 'current_step_index' to determine the next node.
    """
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)
    
    # If no plan or finished all steps, END
    if not plan or current_index >= len(plan):
        return {"next": "FINISH"}
    
    # Get next step node name
    next_node = plan[current_index]["node"]
    
    # Update index for next iteration (this logic assumes the routed node will return back here)
    # BUT: The node itself should probably not increment the index, the supervisor should do it AFTER return?
    # LangGraph nodes return state updates. 
    # If we increment here, we might skip.
    # Strategy: 
    # 1. Supervisor routes to Node X.
    # 2. Node X runs, returns state update.
    # 3. Flow comes back to Supervisor.
    # 4. Supervisor needs to know "I just finished step N, so go to N+1".
    
    # To handle this statelessly within the graph:
    # We can increment the index *before* routing? No, that would be confusing.
    # We can rely on the fact that this node runs *between* steps.
    # Let's assume the nodes update their own status or we just increment here?
    # Actually, we need to know if the *previous* step succeeded. 
    # For simplicity, let's assume success.
    
    # Wait, if we just return {"next": next_node}, the graph goes to next_node.
    # After next_node finishes, it must come back to Supervisor.
    # So Supervisor is hit multiple times.
    # We need to increment the index *somewhere*.
    # Let's increment it *here* and pass the *current* (non-incremented) target to the router?
    # No, better: The Nodes (SelectTables etc) shouldn't care about the plan index.
    # So Supervisor must increment it. 
    
    # Problem: If Supervisor runs, increments index to 1, routes to Step 0.
    # Step 0 runs, returns to Supervisor.
    # Supervisor runs, sees index 1, increments to 2, routes to Step 1.
    # This works!
    
    # So:
    # 1. Get current target from plan[current_index].
    # 2. Increment current_step_index by 1.
    # 3. Return next route.
    
    # Special Case: ClarifyIntent
    # If ClarifyIntent returns "intent_clear=False", we should probably pause or abort plan?
    # Or ClarifyIntent is just a step.
    
    return {
        "next": next_node,
        "current_step_index": current_index + 1
    }
