import re
import json
import difflib
from src.workflow.state import AgentState
from src.core.database import get_query_db
from src.core.dsl.compiler import DSLCompiler
from src.core.mapping import load_column_mapping, apply_mapping_to_ref
from src.domain.schema.search import get_schema_searcher
from langchain_core.messages import AIMessage
from src.domain.schema.join_infer import infer_join_candidates
from sqlglot import parse_one, exp

from src.core.event_bus import EventBus

def _quote_case_identifiers(sql_str: str) -> str:
    try:
        tree = parse_one(sql_str)
        def walk(e):
            if isinstance(e, exp.Column):
                parts = e.parts
                if parts:
                    ident = parts[-1]
                    if isinstance(ident, exp.Identifier):
                        name = ident.this
                        if name and name != name.lower():
                            ident.set("quoted", True)
            for v in e.args.values():
                if isinstance(v, list):
                    for c in v:
                        if isinstance(c, exp.Expression):
                            walk(c)
                elif isinstance(v, exp.Expression):
                    walk(v)
        walk(tree)
        out = tree.to_sql()
        def repl(m):
            left = m.group(1)
            col = m.group(2)
            if col != col.lower() and not (col.startswith('"') and col.endswith('"')):
                return f"{left}.\"{col}\""
            return m.group(0)
        out = re.sub(r'(\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)\.([A-Za-z][A-Za-z0-9_]*)', repl, out)
        out = re.sub(r'((?:"[A-Za-z][A-Za-z0-9_]*"|[A-Za-z_][A-Za-z0-9_]*)(?:\.(?:"[A-Za-z][A-Za-z0-9_]*"|[A-Za-z_][A-Za-z0-9_]*))?)::interval\b', r"\1 * interval '1 day'", out)
        return out
    except Exception:
        out = sql_str
        def repl(m):
            left = m.group(1)
            col = m.group(2)
            if col != col.lower() and not (col.startswith('"') and col.endswith('"')):
                return f"{left}.\"{col}\""
            return m.group(0)
        out = re.sub(r'(\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)\.([A-Za-z][A-Za-z0-9_]*)', repl, out)
        out = re.sub(r'((?:"[A-Za-z][A-Za-z0-9_]*"|[A-Za-z_][A-Za-z0-9_]*)(?:\.(?:"[A-Za-z][A-Za-z0-9_]*"|[A-Za-z_][A-Za-z0-9_]*))?)::interval\b', r"\1 * interval '1 day'", out)
        return out

async def dsl_to_sql_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering dsl_to_sql_node (Async) - Using Code Compiler")
    try:
        project_id = config.get("configurable", {}).get("project_id") if config else None
        
        dsl_str = state.get("dsl")
        
        # Emit Status
        await EventBus.emit_substep(node="DSLtoSQL", step="解析中", detail="正在解析 DSL 结构...")

        print(f"DEBUG: dsl_to_sql_node input dsl: {dsl_str}")
        # 前置拦截：非 JSON 内容（澄清/文本）直接返回意图不清晰
        if isinstance(dsl_str, str) and not dsl_str.strip().startswith("{"):
            return {
                "intent_clear": False,
                "clarify_answer": None  # 强制清除旧的澄清答案，避免 Supervisor 误判
            }
        
        # 1. 获取数据库类型 (Dialect)
        db_type = "mysql" # 默认
        try:
            query_db = get_query_db(project_id)
            if query_db.type == "postgresql":
                db_type = "postgresql"
            elif query_db.type == "mysql":
                db_type = "mysql"
        except Exception as e:
            print(f"DEBUG: Failed to detect DB type, defaulting to MySQL: {e}")
        
        print(f"DEBUG: Detected DB Type: {db_type}")

        # 2. 解析 DSL JSON
        try:
            # 清理可能的 Markdown
            cleaned_dsl = dsl_str.strip()
            if "```json" in cleaned_dsl:
                cleaned_dsl = cleaned_dsl.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_dsl:
                cleaned_dsl = cleaned_dsl.split("```")[1].split("```")[0].strip()
            # 去除行内 // 注释与块注释 /* ... */，提高对 LLM 输出的容错
            def _strip_comments(s: str) -> str:
                # 去掉 // 注释
                s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)
                # 去掉 /* ... */ 注释
                s = re.sub(r"/\*[\s\S]*?\*/", "", s, flags=re.MULTILINE)
                return s
            cleaned_dsl = _strip_comments(cleaned_dsl)
            
            # 尝试直接解析
            try:
                # 支持数组输入的回退（仅取首个查询）
                if cleaned_dsl.strip().startswith("["):
                    arr = json.loads(cleaned_dsl)
                    if isinstance(arr, list) and arr:
                        dsl_json = arr[0]
                    else:
                        raise ValueError("Empty DSL array")
                else:
                    dsl_json = json.loads(cleaned_dsl)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取最外层的大括号内容
                # 这能处理 "Here is the JSON: {...} some other text" 的情况
                print("DEBUG: JSON parse failed, attempting regex extraction...")
                # 进一步处理“多顶层对象并列”的情况：提取所有平衡对象，取第一个
                def extract_json_objects(s: str) -> list[str]:
                    objs = []
                    stack = []
                    start = None
                    for i,ch in enumerate(s):
                        if ch == "{":
                            stack.append("{")
                            if start is None:
                                start = i
                        elif ch == "}":
                            if stack:
                                stack.pop()
                                if not stack and start is not None:
                                    objs.append(s[start:i+1])
                                    start = None
                    return objs
                candidates = extract_json_objects(cleaned_dsl)
                if candidates:
                    try:
                        dsl_json = json.loads(_strip_comments(candidates[0]))
                    except Exception as _:
                        # 最后一搏：贪婪正则
                        match = re.search(r'(\{.*\})', cleaned_dsl, re.DOTALL)
                        if match:
                            json_candidate = _strip_comments(match.group(1))
                            dsl_json = json.loads(json_candidate)
                        else:
                            raise ValueError("No JSON object found in output")
                else:
                    raise ValueError("No JSON object found in output")
                    
        except Exception as e:
            print(f"Error parsing DSL JSON: {e}")
            await EventBus.emit_substep(node="DSLtoSQL", step="错误", detail="DSL 格式解析失败，请求澄清")
            # 友好返回，不抛异常，走澄清路径
            return {"intent_clear": False}
            
        # 3. 编译 SQL
        # 3.0 应用列映射与默认 schema 前缀
        try:
            colmap = load_column_mapping()
            # 规范化列定义：支持 expression 字段；支持仅 agg 的 COUNT(*) 规范化
            def normalize_coldefs(col_defs: list[dict]) -> list[dict]:
                out = []
                for cd in col_defs or []:
                    expr = cd.get("expression")
                    if expr and not cd.get("name"):
                        cd["name"] = expr
                    # 处理仅有聚合函数的列，如 {"name":"count","agg":"COUNT"} -> COUNT(*)
                    agg = cd.get("agg")
                    name_lower = str(cd.get("name", "")).lower()
                    if agg:
                        agg_upper = str(agg).upper()
                        if agg_upper == "COUNT":
                            # 如果 name 已经是聚合表达式，移除 agg，避免双重包装
                            if "count(" in name_lower or name_lower == "count(*)":
                                cd["agg"] = None
                            else:
                                # 将 COUNT 聚合内联到 name，并移除 agg
                                base = cd.get("name", "*")
                                if base in ("*", ""):
                                    cd["name"] = "COUNT(*)"
                                else:
                                    cd["name"] = f"COUNT({base})"
                                cd["agg"] = None
                        # 其他聚合类型保持原样
                    out.append(cd)
                return out
            dsl_json["columns"] = normalize_coldefs(dsl_json.get("columns", []))
            def map_coldefs(col_defs: list[dict]) -> list[dict]:
                out = []
                for cd in col_defs or []:
                    name = cd.get("name")
                    alias = cd.get("alias")
                    tname = cd.get("table")
                    if name:
                        base = name
                        if "." in base and not tname:
                            parts = base.split(".", 1)
                            tname = parts[0]
                            base = parts[1]
                        ref = f"{tname}.{base}" if tname else base
                        mapped = apply_mapping_to_ref(ref, colmap)
                        if mapped != ref:
                            if "." in mapped:
                                mt, mc = mapped.split(".", 1)
                                cd["table"] = mt
                                cd["name"] = mc
                            else:
                                cd["name"] = mapped
                    if alias:
                        cd["alias"] = alias
                    out.append(cd)
                return out
            dsl_json["columns"] = map_coldefs(dsl_json.get("columns", []))
            def map_expr(expr):
                if not expr:
                    return expr
                s = json.dumps(expr, ensure_ascii=False)
                tokens = sorted(set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*\\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*", s)), key=len, reverse=True)
                for tok in tokens:
                    mapped = apply_mapping_to_ref(tok, colmap)
                    if mapped != tok:
                        s = s.replace(tok, mapped)
                return json.loads(s)
            dsl_json["where"] = map_expr(dsl_json.get("where"))
            dsl_json["having"] = map_expr(dsl_json.get("having"))
            dsl_json["order_by"] = map_expr(dsl_json.get("order_by"))
            dsl_json["group_by"] = map_expr(dsl_json.get("group_by"))
            for j in dsl_json.get("joins", []) or []:
                on = j.get("on")
                if isinstance(on, str):
                    parts = re.split(r"(=|<>|!=|>=|<=|>|<)", on)
                    rebuilt = ""
                    for p in parts:
                        if p and p.strip() and "." in p.strip() and p.strip()[0].isalnum():
                            mp = apply_mapping_to_ref(p.strip(), colmap)
                            rebuilt += mp
                        else:
                            rebuilt += p
                    j["on"] = rebuilt
            from src.core.config import settings
            default_schema = getattr(settings, "DEFAULT_QUERY_SCHEMA", "") or ""
            if default_schema:
                def ensure_prefix(tn: str) -> str:
                    if not isinstance(tn, str) or not tn:
                        return tn
                    if "." not in tn:
                        return f"{default_schema}.{tn}"
                    return tn
                if isinstance(dsl_json.get("from"), str):
                    dsl_json["from"] = ensure_prefix(dsl_json["from"])
                for j in dsl_json.get("joins", []) or []:
                    jt = j.get("table")
                    if isinstance(jt, str):
                        j["table"] = ensure_prefix(jt)
        except Exception as _:
            pass
        # 3.1 Schema 预检
        try:
            await EventBus.emit_substep(node="DSLtoSQL", step="静态校验", detail="正在检查 Schema 合法性...")
            
            searcher = get_schema_searcher(project_id)
            # 获取可用的 schema map：table -> set(columns)
            schema_map = {}
            issues = []
            try:
                full_schema = searcher._get_schema()
                for t, info in full_schema.items():
                    cols = set([c["name"] for c in info.get("columns", [])]) if isinstance(info, dict) else set()
                    schema_map[t] = cols
            except Exception as e:
                print(f"DEBUG: Precheck - load schema failed: {e}")
            
            if not schema_map:
                await EventBus.emit_substep(node="DSLtoSQL", step="跳过校验", detail="元数据不可用，跳过静态校验")
                missing_tables = []
                missing_columns = []
                extra_missing = []
                join_on_missing = []
                selected_tables = set()
                if isinstance(dsl_json.get("from"), str):
                    selected_tables.add(dsl_json["from"])
            else:
                def table_exists(tn: str) -> bool:
                    return tn in schema_map
                def column_exists(tn: str, cn: str) -> bool:
                    if not tn:
                        # 无表前缀时，仅做宽松检查：列名出现在任何已选表中
                        for _t in selected_tables:
                            if cn in schema_map.get(_t, set()):
                                return True
                        return False
                    return cn in schema_map.get(tn, set())
                
                # 选中表集合
                selected_tables = set()
                if isinstance(dsl_json.get("from"), str):
                    selected_tables.add(dsl_json["from"])
                for j in dsl_json.get("joins", []) or []:
                    jt = j.get("table")
                    if isinstance(jt, str):
                        selected_tables.add(jt)
                
                # 校验表存在
                missing_tables = [t for t in selected_tables if not table_exists(t)]
                
                # 解析列清单
                col_defs = dsl_json.get("columns", []) or []
                missing_columns = []
                # 列别名集合
                aliases = set()
                for cd in col_defs:
                    name = cd.get("name")
                    tname = cd.get("table")
                    alias = cd.get("alias")
                    if alias:
                        aliases.add(alias)
                    if name:
                        base = name
                        m = re.match(r"(?i)\s*(?:sum|count|avg|min|max)\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)\s*$", base or "")
                        if m:
                            base = m.group(1)
                            if "." in base and not tname:
                                parts = base.split(".", 1)
                                tname = parts[0]
                                base = parts[1]
                            if tname and not table_exists(tname):
                                if tname not in missing_tables:
                                     missing_tables.append(tname)
                            elif base and base != "*" and not column_exists(tname, base):
                                missing_columns.append(f"{tname+'.' if tname else ''}{base}")
                        else:
                            tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*", base or "")
                            func_names = {"date_trunc","to_timestamp","cast","coalesce","extract","concat"}
                            keywords = {"interval","current_date","current_timestamp","true","false","null"}
                            for tok in tokens:
                                tl = tok.lower()
                                if tl in func_names or tl in keywords:
                                    continue
                                if re.match(r"^[0-9]+$", tok):
                                    continue
                                if "." in tok:
                                    tn, cn = tok.split(".", 1)
                                    if not table_exists(tn):
                                        if tn not in missing_tables:
                                            missing_tables.append(tn)
                                    elif not column_exists(tn, cn):
                                        missing_columns.append(f"{tn}.{cn}")
                                else:
                                    if tok != "*" and not column_exists(None, tok):
                                        missing_columns.append(tok)

                # 递归遍历 WHERE/HAVING 条件
                def collect_condition_columns(cond):
                    cols = []
                    if not cond:
                        return cols
                    if "logic" in cond and "conditions" in cond:
                        for sub in cond.get("conditions", []):
                            cols.extend(collect_condition_columns(sub))
                    elif "column" in cond:
                        c = cond["column"]
                        # Handle aggregate in condition e.g. sum(amount)
                        m = re.match(r"(?i)\s*(?:sum|count|avg|min|max)\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)\s*$", c or "")
                        if m:
                            cols.append(m.group(1))
                        else:
                            cols.append(c)
                    return cols

                where_cols = collect_condition_columns(dsl_json.get("where"))
                having_cols = collect_condition_columns(dsl_json.get("having"))
                
                # Group By / Order By
                group_cols = dsl_json.get("group_by") or []
                order_cols = [o.get("column") for o in (dsl_json.get("order_by") or []) if isinstance(o, dict)]
                
            def verify_ref(colref: str):
                if not colref:
                    return None
                if colref in aliases:
                    return None
                s = str(colref)
                if s.upper() in ["TRUE", "FALSE", "NULL"]:
                    return None
                # 如果是复杂表达式，提取其中的列引用进行逐项校验
                if any(ch in s for ch in ("(", ")", " ", "-", "+", "*", "/", ":", "'", '"')):
                    func_names = {"date_trunc","to_timestamp","cast","coalesce","extract","concat"}
                    keywords = {"interval","current_date","current_timestamp"}
                    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*", s)
                    for tok in tokens:
                        tl = tok.lower()
                        if tl in func_names or tl in keywords:
                            continue
                        if re.match(r"^[0-9]+$", tok):
                            continue
                        if "." in tok:
                            tn, cn = tok.split(".", 1)
                            if not table_exists(tn):
                                return f"表不存在: {tn}"
                            if not column_exists(tn, cn):
                                return f"列不存在: {tn}.{cn}"
                        else:
                            # 裸列必须存在于选中表之一
                            found = any(column_exists(t, tok) for t in selected_tables)
                            if not found:
                                return f"列不存在: {tok}"
                    return None
                # 简单引用直接校验
                if "." in s:
                    tn, cn = s.split(".", 1)
                    if not table_exists(tn):
                        return f"表不存在: {tn}"
                    if not column_exists(tn, cn):
                        return f"列不存在: {tn}.{cn}"
                else:
                    found = any(column_exists(t, s) for t in selected_tables)
                    if not found:
                        return f"列不存在: {s}"
                return None

                extra_missing = []
                for col in where_cols + having_cols + group_cols + order_cols:
                    err = verify_ref(col)
                    if err:
                        extra_missing.append(err)

                # 解析并校验 JOIN ON
                join_on_missing = []
                for j in dsl_json.get("joins", []) or []:
                    on = j.get("on")
                    if isinstance(on, str) and on.strip():
                        # 简单的正则提取
                        # 提取所有 word.word 或 word
                        tokens = re.findall(r"([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)", on)
                        for tok in tokens:
                            tn, cn = tok.split(".", 1)
                            if not table_exists(tn):
                                 join_on_missing.append(f"JOIN 引用的表不存在: {tn}")
                            elif not column_exists(tn, cn):
                                 join_on_missing.append(f"JOIN 引用的列不存在: {tn}.{cn}")

                issues = []
                if missing_tables:
                    issues.append("不存在的表: " + ", ".join(sorted(set(missing_tables))))
                if missing_columns:
                    issues.append("不存在的列: " + ", ".join(sorted(set(missing_columns))))
                if extra_missing:
                    issues.append("引用错误: " + ", ".join(sorted(set(extra_missing))))
                if join_on_missing:
                    issues.append("JOIN 条件错误: " + "; ".join(sorted(set(join_on_missing))))

            # 若存在澄清答案，尝试应用后再验证一次，避免重复澄清
            clarify = state.get("clarify_answer") or {}
            if issues and isinstance(clarify, dict) and clarify.get("choices"):
                choices = clarify.get("choices") or []
                def parse_choice(ch: str):
                    if not isinstance(ch, str):
                        return None, None
                    if "." in ch:
                        tn, cn = ch.split(".", 1)
                        return tn, cn
                    return None, ch
                # 取第一个选择作为修复目标（简单策略）
                tn_fix, cn_fix = parse_choice(choices[0])
                def replace_ref(colref: str) -> str:
                    if not colref:
                        return colref
                    # 若已有表前缀，直接用选择的列名替换列部分；否则使用选择提供的表列或仅列
                    if "." in colref:
                        tn, _ = colref.split(".", 1)
                        target_tn = tn_fix or tn
                        return f"{target_tn}.{cn_fix}"
                    else:
                        return f"{tn_fix}.{cn_fix}" if tn_fix else cn_fix
                # 应用到 columns
                new_cols = []
                for cd in dsl_json.get("columns", []) or []:
                    name = cd.get("name")
                    alias = cd.get("alias")
                    if name and name != "*":
                        m = re.match(r"(?i)\s*(?:sum|count|avg|min|max)\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)\s*$", name or "")
                        if m:
                            base = replace_ref(m.group(1))
                            func = name.split("(")[0].strip()
                            cd["name"] = f"{func}({base})"
                        else:
                            cd["name"] = replace_ref(name)
                    if alias:
                        cd["alias"] = alias
                    new_cols.append(cd)
                dsl_json["columns"] = new_cols
                # 递归替换 where/having/group/order
                def mutate_conditions(cond):
                    if not cond:
                        return cond
                    if "logic" in cond and "conditions" in cond:
                        cond["conditions"] = [mutate_conditions(c) for c in cond.get("conditions", [])]
                        return cond
                    if "column" in cond:
                        c = cond["column"]
                        m = re.match(r"(?i)\s*(?:sum|count|avg|min|max)\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)\s*$", c or "")
                        if m:
                            base = replace_ref(m.group(1))
                            func = c.split("(")[0].strip()
                            cond["column"] = f"{func}({base})"
                        else:
                            cond["column"] = replace_ref(c)
                        return cond
                    return cond
                dsl_json["where"] = mutate_conditions(dsl_json.get("where"))
                dsl_json["having"] = mutate_conditions(dsl_json.get("having"))
                # group_by / order_by
                dsl_json["group_by"] = [replace_ref(g) for g in (dsl_json.get("group_by") or [])]
                dsl_json["order_by"] = [{"column": replace_ref(o.get("column")), **{k:v for k,v in o.items() if k != "column"}} for o in (dsl_json.get("order_by") or []) if isinstance(o, dict)]
                # 重新验证
                issues = []
                missing_tables = [t for t in selected_tables if not table_exists(t)]
                if missing_tables:
                    issues.append("不存在的表: " + ", ".join(sorted(set(missing_tables))))
                # 重新收集列
                def collect_all_columns():
                    cols = []
                    for cd in dsl_json.get("columns", []) or []:
                        n = cd.get("name")
                        if n and n != "*":
                            m = re.match(r"(?i)\s*(?:sum|count|avg|min|max)\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)\s*$", n or "")
                            cols.append(m.group(1) if m else n)
                    cols += where_cols + having_cols + dsl_json.get("group_by") + [o.get("column") for o in dsl_json.get("order_by") or [] if isinstance(o, dict)]
                    return cols
                re_cols = collect_all_columns()
                extra_missing = []
                missing_columns = []
                for col in re_cols:
                    err = verify_ref(col)
                    if err:
                        if "列不存在" in err:
                            missing_columns.append(col)
                        else:
                            extra_missing.append(err)
                if missing_columns:
                    issues.append("不存在的列: " + ", ".join(sorted(set(missing_columns))))
                if extra_missing:
                    issues.append("引用错误: " + ", ".join(sorted(set(extra_missing))))

            if issues:
                await EventBus.emit_substep(node="DSLtoSQL", step="校验失败", detail=f"发现 {len(issues)} 个问题，请求澄清")
                # 构造澄清选项
                options = []
                for t in sorted(selected_tables):
                    cols = list(schema_map.get(t, set()))
                    for c in cols[:10]:
                        options.append(f"{t}.{c}")
                
                suggestions = []
                # ... (Keep suggestion logic similar or simplified) ...
                
                question = "检测到 DSL 引用了不存在的表/列或无效 JOIN，请选择正确的字段："
                payload = {
                    "status":"AMBIGUOUS",
                    "question": question,
                    "options": options[:20],
                    "type":"multiple",
                    "suggestions": suggestions[:10],
                    "error_details": issues 
                }
                json_content = json.dumps(payload, ensure_ascii=False)
                return {
                    "intent_clear": False,
                    "clarify_answer": None, 
                    "clarify": payload,     
                    "messages": [AIMessage(content=json_content)]
                }
            else:
                await EventBus.emit_substep(node="DSLtoSQL", step="校验通过", detail="DSL 结构与 Schema 一致")
        except Exception as e:
            print(f"DEBUG: Precheck failed with exception: {e}")
            pass
        # 3.2 编译 SQL
        compiler = DSLCompiler(dialect=db_type)
        try:
            sql = compiler.compile(dsl_json)
            print(f"DEBUG: Compiled SQL: {sql}")
            sql = _quote_case_identifiers(sql)
            await EventBus.emit_substep(node="DSLtoSQL", step="编译完成", detail="SQL 已生成")
        except Exception as e:
            print(f"Error compiling SQL: {e}")
            await EventBus.emit_substep(node="DSLtoSQL", step="错误", detail=f"编译失败: {str(e)}")
            raise ValueError(f"DSL Compilation Failed: {e}")

        return {"sql": sql}
        
    except Exception as e:
        print(f"ERROR in dsl_to_sql_node: {e}")
        return {
            "intent_clear": False,
            "clarify_answer": None
        }
