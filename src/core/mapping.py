import json
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def load_column_mapping() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "column_mapping.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def apply_mapping_to_ref(ref: str, mapping: dict) -> str:
    if not isinstance(ref, str) or not ref:
        return ref
    if ref in mapping:
        return mapping[ref]
    if "." in ref:
        tn, cn = ref.split(".", 1)
        key = f"{tn}.{cn}"
        return mapping.get(key, ref)
    return mapping.get(ref, ref)
