import re

def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9_]', '', s)
    s = s.replace('__', '_')
    return s

def _sim(a: str, b: str) -> float:
    a = _norm(a)
    b = _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.endswith('_id') and b == 'id':
        return 0.9
    if b.endswith('_id') and a == 'id':
        return 0.9
    if a.replace('_id', '') == b.replace('_id', ''):
        return 0.85
    la = len(a)
    lb = len(b)
    lcs = 0
    for i in range(la):
        for j in range(lb):
            k = 0
            while i+k < la and j+k < lb and a[i+k] == b[j+k]:
                k += 1
            if k > lcs:
                lcs = k
    return lcs / max(la, lb)

def _type_weight(t: str) -> float:
    ts = str(t).lower()
    if any(x in ts for x in ['int', 'bigint', 'smallint']):
        return 0.8
    if 'uuid' in ts:
        return 0.75
    if 'varchar' in ts or 'char' in ts:
        return 0.6
    if 'text' in ts:
        return 0.3
    if 'date' in ts or 'time' in ts or 'timestamp' in ts:
        return 0.2
    return 0.4

def _is_key_like(name: str) -> bool:
    n = _norm(name)
    if n == 'id':
        return True
    if n.endswith('_id'):
        return True
    if n.endswith('id'):
        return True
    return False

def _uniq_bonus(col_name: str, table_info: dict) -> float:
    bonus = 0.0
    if not table_info:
        return bonus
    pk = table_info.get('primary_key') or []
    if col_name in pk:
        bonus += 0.3
    for ix in table_info.get('indexes') or []:
        if bool(ix.get('unique')) and col_name in (ix.get('column_names') or []):
            bonus += 0.2
            break
    return bonus

def infer_join_candidates(table_a: str, table_b: str, schema_map: dict, top_k: int = 5) -> list[tuple[str, float]]:
    info_a = schema_map.get(table_a) or {}
    info_b = schema_map.get(table_b) or {}
    cols_a = info_a.get('columns') or []
    cols_b = info_b.get('columns') or []
    cands = []
    for ca in cols_a:
        na = ca.get('name')
        ta = ca.get('type')
        for cb in cols_b:
            nb = cb.get('name')
            tb = cb.get('type')
            s = 0.0
            s += _sim(na, nb)
            s += 0.15 if _is_key_like(na) else 0.0
            s += 0.15 if _is_key_like(nb) else 0.0
            s += 0.3 if _norm(na).endswith('_id') or _norm(nb).endswith('_id') else 0.0
            s += (_type_weight(str(ta)) + _type_weight(str(tb))) * 0.25
            s += _uniq_bonus(na, info_a) * 0.5
            s += _uniq_bonus(nb, info_b) * 0.5
            if s > 0.9:
                on = f"{table_a}.{na} = {table_b}.{nb}"
                cands.append((on, s))
    cands.sort(key=lambda x: x[1], reverse=True)
    return cands[:top_k]

