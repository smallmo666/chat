import re
from src.workflow.state import AgentState
from src.domain.schema.search import get_schema_searcher
from langchain_core.messages import AIMessage
from src.core.event_bus import EventBus
import json

async def schema_guard_node(state: AgentState, config: dict = None) -> dict:
    project_id = config.get("configurable", {}).get("project_id") if config else None
    
    await EventBus.emit_substep(node="SchemaGuard", step="分析中", detail="正在检查 Schema 歧义...")
    
    searcher = get_schema_searcher(project_id)
    schema = {}
    try:
        full = searcher._get_schema()
        for t, info in full.items():
            cols = [c["name"] for c in info.get("columns", [])] if isinstance(info, dict) else []
            schema[t] = cols
    except Exception as _:
        schema = {}
    rel = state.get("relevant_schema", "") or ""
    tables = []
    for line in rel.split("\n"):
        if line.startswith("表名:"):
            m = re.match(r"表名:\s*([A-Za-z0-9_.]+)", line)
            if m:
                tables.append(m.group(1))
        elif line.startswith("Table:"):
            m = re.match(r"Table:\s*([A-Za-z0-9_.]+)", line)
            if m:
                tables.append(m.group(1))
    if not tables and schema:
        tables = list(schema.keys())[:5]
    if not tables:
        sel = state.get("selected_tables") or []
        if sel:
            tables = sel
    allowed = {}
    for t in tables:
        if t in schema:
            allowed[t] = schema[t]
        else:
            if "." in t:
                suffix = t.split(".", 1)[1]
                for k in schema.keys():
                    if k.endswith("." + suffix):
                        allowed[k] = schema[k]
                        break
    if not allowed:
        if tables and not schema:
            await EventBus.emit_substep(node="SchemaGuard", step="回退", detail="元数据不可用，使用最小约束继续")
            fallback_allowed = {t: [] for t in tables}
            return {
                "intent_clear": True,
                "allowed_schema": fallback_allowed,
                "last_executed_node": "SchemaGuard"
            }
        await EventBus.emit_substep(node="SchemaGuard", step="发现歧义", detail="无法确定目标表，请求澄清")
        opts = list(schema.keys())[:20]
        payload = {
            "status": "AMBIGUOUS",
            "question": "请选择用于生成查询的具体表",
            "options": opts,
            "type": "select"
        }
        return {
            "intent_clear": False,
            "clarify": payload,
            "messages": [AIMessage(content=json.dumps(payload, ensure_ascii=False))]
        }
        
    await EventBus.emit_substep(node="SchemaGuard", step="检查通过", detail=f"已锁定 {len(allowed)} 个有效表")
    return {
        "intent_clear": True,
        "allowed_schema": allowed,
        "last_executed_node": "SchemaGuard"
    }
