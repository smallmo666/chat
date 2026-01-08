import asyncio
import re
import json

from src.workflow.nodes.dsl2sql import dsl_to_sql_node
from src.workflow.state import AgentState
from src.core.config import settings
from src.core.models import AuditLog
from sqlalchemy import Text
from src.core.dsl.compiler import DSLCompiler
from src.core.mapping import apply_mapping_to_ref, load_column_mapping

class FakeSearcher:
    def __init__(self, schema: dict):
        self._schema = schema
    def _get_schema(self):
        return self._schema

def test_dsl_precheck_missing_column(monkeypatch):
    schema = {
        "reverse_logistics.products": {
            "columns": [{"name": "itemcode"}, {"name": "itemcategory"}, {"name": "subcat"}]
        },
        "reverse_logistics.orders": {
            "columns": [{"name": "refund_status"}, {"name": "txn_date"}]
        }
    }
    def fake_get_schema_searcher(project_id):
        return FakeSearcher(schema)
    monkeypatch.setattr("src.workflow.nodes.dsl2sql.get_schema_searcher", fake_get_schema_searcher)
    dsl = {
        "command": "SELECT",
        "from": "reverse_logistics.products",
        "columns": [
            {"name": "itemcode", "table": "reverse_logistics.products"},
            {"name": "itemcategory", "table": "reverse_logistics.products"},
            {"name": "subcat", "table": "reverse_logistics.products"}
        ],
        "joins": [
            {"table": "reverse_logistics.orders", "type": "INNER", "on": "reverse_logistics.products.itemcode = reverse_logistics.orders.itemcode"}
        ],
        "where": {"logic":"AND","conditions":[{"column":"reverse_logistics.orders.txndate","op":">=","value":"2025-01-01"}]},
        "group_by": ["reverse_logistics.products.itemcode", "reverse_logistics.products.itemcategory", "reverse_logistics.products.subcat"],
        "order_by": [{"column": "refund_rate", "direction": "DESC"}],
        "limit": 10
    }
    state = {
        "messages": [],
        "next": "",
        "dsl": json.dumps(dsl),
        "sql": None,
        "results": None,
        "intent_clear": True,
        "relevant_schema": None,
        "rewritten_query": None,
        "manual_selected_tables": None,
        "hypotheses": None,
        "analysis_depth": "simple",
        "plan": [],
        "current_step_index": 0,
        "visualization": None,
        "analysis": None,
        "python_code": None,
        "insights": None,
        "ui_component": None,
        "knowledge_context": None,
        "error": None,
        "retry_count": 0,
        "plan_retry_count": 0
    }
    res = asyncio.run(dsl_to_sql_node(state, config={"configurable": {"project_id": 1}}))
    assert res.get("intent_clear") is False
    msgs = res.get("messages", [])
    assert msgs, "should return clarification messages"

def test_dsl_mapping_and_schema_prefix(monkeypatch):
    settings.DEFAULT_QUERY_SCHEMA = "reverse_logistics"
    schema = {
        "reverse_logistics.products": {
            "columns": [{"name": "itemcode"}]
        },
        "reverse_logistics.orders": {
            "columns": [{"name": "product_code"}, {"name": "txn_date"}, {"name": "refund_status"}]
        }
    }
    def fake_get_schema_searcher(project_id):
        return FakeSearcher(schema)
    monkeypatch.setattr("src.workflow.nodes.dsl2sql.get_schema_searcher", fake_get_schema_searcher)
    dsl = {
        "command": "SELECT",
        "from": "products",
        "columns": [
            {"name": "itemcode", "table": "products"},
            {"name": "refund_status", "table": "orders"}
        ],
        "joins": [
            {"table": "orders", "type": "INNER", "on": "products.itemcode = orders.itemcode"}
        ],
        "where": {"logic":"AND","conditions":[{"column":"orders.txndate","op":">=","value":"2025-01-01"}]},
        "limit": 1
    }
    state = {
        "messages": [],
        "next": "",
        "dsl": json.dumps(dsl),
        "sql": None,
        "results": None,
        "intent_clear": True,
        "relevant_schema": None,
        "rewritten_query": None,
        "manual_selected_tables": None,
        "hypotheses": None,
        "analysis_depth": "simple",
        "plan": [],
        "current_step_index": 0,
        "visualization": None,
        "analysis": None,
        "python_code": None,
        "insights": None,
        "ui_component": None,
        "knowledge_context": None,
        "error": None,
        "retry_count": 0,
        "plan_retry_count": 0
    }
    colmap = load_column_mapping()
    def ensure_prefix(tn: str) -> str:
        if "." not in tn:
            return f"{settings.DEFAULT_QUERY_SCHEMA}.{tn}"
        return tn
    dsl["from"] = ensure_prefix(dsl["from"])
    for j in dsl["joins"]:
        j["table"] = ensure_prefix(j["table"])
        parts = []
        for p in re.split(r"(=|<>|!=|>=|<=|>|<)", j["on"]):
            if p and p.strip() and "." in p.strip() and p.strip()[0].isalnum():
                parts.append(apply_mapping_to_ref(p.strip(), colmap))
            else:
                parts.append(p)
        j["on"] = "".join(parts)
    def map_expr(expr):
        s = json.dumps(expr)
        toks = sorted(set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*", s)), key=len, reverse=True)
        for tok in toks:
            mt = apply_mapping_to_ref(tok, colmap)
            if mt != tok:
                s = s.replace(tok, mt)
        return json.loads(s)
    dsl["where"] = map_expr(dsl["where"])
    comp = DSLCompiler(dialect="postgresql")
    sql = comp.compile(dsl)
    assert "reverse_logistics" in sql
    assert "product_code" in sql

def test_audit_log_executed_sql_type():
    col = AuditLog.__table__.columns.get("executed_sql")
    assert isinstance(col.type, Text.__class__) or str(col.type).lower().find("text") != -1
