import json
import hashlib
import time
from typing import Dict
from src.core.redis_client import get_sync_redis_client
from src.core.config import settings

SNAP_TTL = getattr(settings, "REDIS_SCHEMA_TTL", 3600 * 24)

SNAP_FIELDS = [
    "messages", "plan", "current_step_index", "dsl", "sql", "results",
    "intent_clear", "relevant_schema", "rewritten_query", "manual_selected_tables",
    "last_executed_node", "clarify_pending", "clarify_payload", "clarify_answer",
    "clarify_retry_count", "analysis_depth", "visualization", "analysis", "python_code",
    "insights", "ui_component", "knowledge_context", "error", "retry_count", "plan_retry_count"
]

def _snap_key(project_id: int, thread_id: str, token: str) -> str:
    return f"t2s:v1:snap:{project_id}:{thread_id}:{token}"

def save_snapshot(state: Dict, project_id: int, thread_id: str, token: str) -> None:
    snap = {}
    for f in SNAP_FIELDS:
        if f in state:
            snap[f] = state.get(f)
    # 压缩 messages：仅保留最近 20 条
    msgs = snap.get("messages")
    if isinstance(msgs, list) and len(msgs) > 20:
        snap["messages"] = msgs[-20:]
    client = get_sync_redis_client()
    client.setex(_snap_key(project_id, thread_id, token), SNAP_TTL, json.dumps(snap, ensure_ascii=False))

def load_snapshot(project_id: int, thread_id: str, token: str) -> Dict | None:
    client = get_sync_redis_client()
    raw = client.get(_snap_key(project_id, thread_id, token))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def gen_snapshot_token(state: Dict) -> str:
    base = json.dumps({
        "ts": time.time(),
        "plan_len": len(state.get("plan", []) or []),
        "idx": state.get("current_step_index", 0),
        "hash": hashlib.md5((state.get("sql") or "" + state.get("dsl") or "").encode()).hexdigest()
    })
    return hashlib.md5(base.encode()).hexdigest()[:16]

