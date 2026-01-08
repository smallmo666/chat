from typing import List, Dict, Any
import json
import time

def _now() -> int:
    return int(time.time() * 1000)

def _planner(update: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    rq = update.get("rewritten_query")
    plan = update.get("plan", [])
    if rq:
        items.append({"node": "Planner", "step": "intent_rewrite", "detail": "意图重写", "ts": _now()})
    items.append({"node": "Planner", "step": "plan_generated", "detail": f"任务数 {len(plan)}", "ts": _now()})
    return items

def _clarify(update: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    if update.get("intent_clear"):
        items.append({"node": "ClarifyIntent", "step": "intent_clear", "detail": "澄清完成", "ts": _now()})
    else:
        payload = update.get("clarify") or {}
        q = payload.get("question", "")
        t = payload.get("type", "select")
        scope = payload.get("scope", "schema")
        items.append({"node": "ClarifyIntent", "step": "clarify_required", "detail": f"{scope}/{t}: {q}", "ts": _now()})
    return items

def _select_tables(update: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    schema = update.get("relevant_schema", "") or ""
    if schema:
        cnt = 0
        for line in schema.split("\n"):
            if line.startswith("### Table: "):
                cnt += 1
        items.append({"node": "SelectTables", "step": "schema_extracted", "detail": f"相关表 {cnt}", "ts": _now()})
    else:
        items.append({"node": "SelectTables", "step": "recall_candidates", "detail": "候选召回与融合", "ts": _now()})
    return items

def _generate_dsl(update: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    dsl_str = update.get("dsl", "")
    agg = []
    dims = []
    order = False
    limit = False
    try:
        dsl = json.loads(dsl_str) if isinstance(dsl_str, str) and dsl_str.strip().startswith("{") else {}
        cols = dsl.get("columns", [])
        for c in cols:
            if isinstance(c, dict) and c.get("agg"):
                agg.append(c.get("agg"))
        dims = dsl.get("group_by", []) or []
        ob = dsl.get("order_by", []) or []
        order = bool(ob)
        limit = bool(dsl.get("limit"))
    except Exception:
        pass
    items.append({"node": "GenerateDSL", "step": "columns_pruned", "detail": f"聚合 {len(agg)} 维度 {len(dims)} 排序 {order} 限制 {limit}", "ts": _now()})
    return items

def _dsl_to_sql(update: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    sql = update.get("sql", "") or ""
    dialect = "postgresql" if "FROM" in sql.upper() else "unknown"
    items.append({"node": "DSLtoSQL", "step": "dialect_adapted", "detail": dialect, "ts": _now()})
    return items

def _execute_sql(update: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    r = update.get("results", "[]")
    try:
        data = json.loads(r) if isinstance(r, str) and r.strip().startswith("[") else []
        rc = len(data) if isinstance(data, list) else 0
        items.append({"node": "ExecuteSQL", "step": "executed", "detail": f"返回 {rc} 行", "ts": _now()})
    except Exception:
        items.append({"node": "ExecuteSQL", "step": "executed", "detail": "执行完成", "ts": _now()})
    return items

_REGISTRY = {
    "Planner": _planner,
    "ClarifyIntent": _clarify,
    "SelectTables": _select_tables,
    "GenerateDSL": _generate_dsl,
    "DSLtoSQL": _dsl_to_sql,
    "ExecuteSQL": _execute_sql,
}

def build_substeps(node_name: str, update: Dict[str, Any], verbosity: str = "medium") -> List[Dict[str, Any]]:
    fn = _REGISTRY.get(node_name)
    if not fn:
        return []
    return fn(update)
