import asyncio
from src.workflow.nodes.schema_guard import schema_guard_node
from src.domain.schema import search as schema_search_module

class DummySearcher:
    def _get_schema(self):
        return {
            "crypto_exchange.users": {"columns": [{"name": "id"}, {"name": "created_at"}]},
            "crypto_exchange.orders": {"columns": [{"name": "id"}]},
        }

async def _run(state):
    orig_get = schema_search_module.get_schema_searcher
    schema_search_module.get_schema_searcher = lambda project_id=None: DummySearcher()
    try:
        return await schema_guard_node(state, config={"configurable": {"project_id": None}})
    finally:
        schema_search_module.get_schema_searcher = orig_get

def test_schema_guard_parses_dot_table_names():
    rel = "表名: crypto_exchange.users\n"
    state = {"relevant_schema": rel}
    out = asyncio.run(_run(state))
    allowed = out.get("allowed_schema")
    assert "crypto_exchange.users" in allowed
