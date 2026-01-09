from src.workflow.nodes.supervisor import supervisor_node

def test_supervisor_downgrade_retry_to_generatedsl():
    plan = [
        {"node": "Planner"},
        {"node": "SelectTables"},
        {"node": "SchemaGuard"},
        {"node": "GenerateDSL"},
    ]
    rel = "表名: crypto_exchange.users\n"
    state = {
        "intent_clear": True,
        "plan": plan,
        "current_step_index": 3,
        "last_executed_node": "SchemaGuard",
        "relevant_schema": rel
    }
    out = supervisor_node(state, config={})
    assert out["next"] == "GenerateDSL"
    assert "allowed_schema" in out
    assert "crypto_exchange.users" in out["allowed_schema"]

