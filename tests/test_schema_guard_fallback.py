import asyncio
from src.workflow.nodes.schema_guard import schema_guard_node
from src.domain.schema import search as schema_search_module

class DummySearcher:
    def _get_schema(self):
        return {}

async def _run(state):
    orig_get = schema_search_module.get_schema_searcher
    schema_search_module.get_schema_searcher = lambda project_id=None: DummySearcher()
    try:
        return await schema_guard_node(state, config={"configurable": {"project_id": None}})
    finally:
        schema_search_module.get_schema_searcher = orig_get

def test_schema_guard_fallback_allowed_schema():
    rel = "表名: crypto_exchange.users\n"
    state = {"relevant_schema": rel}
    out = asyncio.run(_run(state))
    assert out.get("intent_clear") is True
    allowed = out.get("allowed_schema")
    assert isinstance(allowed, dict)
    assert "crypto_exchange.users" in allowed
    assert allowed["crypto_exchange.users"] == []
