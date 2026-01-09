from src.workflow.nodes.supervisor import supervisor_node

def test_supervisor_blocks_on_clarify_pending():
    state = {
        "intent_clear": False,
        "plan": [{"node": "SelectTables"}, {"node": "GenerateDSL"}],
        "current_step_index": 0,
        "clarify": {"question": "Q", "options": ["A"], "type": "select"},
        "clarify_pending": False
    }
    out = supervisor_node(state, config={})
    assert out["next"] == "FINISH"
    assert out.get("clarify_pending") is True

def test_supervisor_global_pending_halt():
    state = {
        "intent_clear": True,
        "plan": [{"node": "SelectTables"}],
        "current_step_index": 0,
        "clarify_pending": True
    }
    out = supervisor_node(state, config={})
    assert out["next"] == "FINISH"

