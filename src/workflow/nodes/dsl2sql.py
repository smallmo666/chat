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

async def dsl_to_sql_node(state: AgentState, config: dict = None) -> dict:
    print("DEBUG: Entering dsl_to_sql_node (Async) - Using Code Compiler")
    try:
        project_id = config.get("configurable", {}).get("project_id") if config else None
        
        dsl_str = state.get("dsl")
        print(f"DEBUG: dsl_to_sql_node input dsl: {dsl_str}")
        # 前置拦截：非 JSON 内容（澄清/文本）直接返回意图不清晰
        if isinstance(dsl_str, str) and not dsl_str.strip().startswith("{"):
            return {"intent_clear": False}
        
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
                        dsl_json = json.loads(candidates[0])
                    except Exception as _:
                        # 最后一搏：贪婪正则
                        match = re.search(r'(\{.*\})', cleaned_dsl, re.DOTALL)
                        if match:
                            json_candidate = match.group(1)
                            dsl_json = json.loads(json_candidate)
                        else:
                            raise ValueError("No JSON object found in output")
                else:
                    raise ValueError("No JSON object found in output")
                    
        except Exception as e:
            print(f"Error parsing DSL JSON: {e}")
            # 友好返回，不抛异常，走澄清路径
            return {"intent_clear": False}
            
        # 3. 编译 SQL
        # 3.0 应用列映射与默认 schema 前缀
        try:
            colmap = load_column_mapping()
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
            searcher = get_schema_searcher(project_id)
            # 获取可用的 schema map：table -> set(columns)
            schema_map = {}
            try:
                full_schema = searcher._get_schema()
                for t, info in full_schema.items():
                    cols = set([c["name"] for c in info.get("columns", [])]) if isinstance(info, dict) else set()
                    schema_map[t] = cols
            except Exception as e:
                print(f"DEBUG: Precheck - load schema failed: {e}")
            
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
                    # 尝试解析函数表达式中的裸列名，简单处理
                    # 例如 sum(amount) -> amount
                    base = name
                    m = re.match(r"(?i)\s*(?:sum|count|avg|min|max)\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)\s*$", base or "")
                    if m:
                        base = m.group(1)
                    # 拆分 table.column
                    if "." in base and not tname:
                        parts = base.split(".", 1)
                        tname = parts[0]
                        base = parts[1]
                    if tname and not table_exists(tname):
                        missing_tables.append(tname)
                    elif base and not column_exists(tname, base):
                        missing_columns.append(f"{tname+'.' if tname else ''}{base}")
            # 校验 WHERE/HAVING、GROUP、ORDER 引用
            def collect_expr_columns(expr):
                cols = []
                if not expr:
                    return cols
                # 递归结构不易解析，这里用正则捕获 table.column 或裸列名
                tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*", json.dumps(expr))
                for tok in tokens:
                    # 跳过操作符/关键词/别名集合已包含的名字
                    if tok.upper() in {"AND","OR","IN","LIKE","NOT","NULL","DESC","ASC"}:
                        continue
                    if tok in aliases:
                        continue
                    cols.append(tok)
                return cols
            where_cols = collect_expr_columns(dsl_json.get("where"))
            having_cols = collect_expr_columns(dsl_json.get("having"))
            group_cols = dsl_json.get("group_by") or []
            order_cols = [o.get("column") for o in (dsl_json.get("order_by") or []) if isinstance(o, dict)]
            def verify_ref(colref: str):
                if not colref:
                    return None
                if colref in aliases:
                    return None
                if "." in colref:
                    tn, cn = colref.split(".", 1)
                    if not table_exists(tn):
                        return f"表不存在: {tn}"
                    if not column_exists(tn, cn):
                        return f"列不存在: {tn}.{cn}"
                else:
                    # 裸列必须至少存在于某个选中表
                    found = any(column_exists(t, colref) for t in selected_tables)
                    if not found:
                        return f"列不存在: {colref}"
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
                    sides = re.split(r"=|<>|!=|>=|<=|>|<", on)
                    for s in sides:
                        s = s.strip()
                        if "." in s:
                            tn, cn = s.split(".", 1)
                            if not table_exists(tn):
                                join_on_missing.append(f"JOIN 引用的表不存在: {tn}")
                            elif not column_exists(tn, cn):
                                join_on_missing.append(f"JOIN 引用的列不存在: {tn}.{cn}")
                else:
                    # 非 table.column 的 ON 引用，宽松通过
                    pass
            issues = []
            if missing_tables:
                issues.append("不存在的表: " + ", ".join(sorted(set(missing_tables))))
            if missing_columns:
                issues.append("不存在的列: " + ", ".join(sorted(set(missing_columns))))
            if extra_missing:
                issues.append("引用错误: " + ", ".join(sorted(set(extra_missing))))
            if join_on_missing:
                issues.append("JOIN 条件错误: " + "; ".join(sorted(set(join_on_missing))))
            if issues:
                # 构造澄清选项：为每个可疑列提供候选
                options = []
                for t in sorted(selected_tables):
                    cols = list(schema_map.get(t, set()))
                    # 仅取前 10 个避免过长
                    for c in cols[:10]:
                        options.append(f"{t}.{c}")
                # 基于相似度的建议：为缺失列提供可能的目标列
                suggestions = []
                def suggest_for_missing(miss_list):
                    for m in miss_list:
                        base = m.split(".", 1)[-1]
                        candidates = []
                        for t in sorted(selected_tables):
                            candidates.extend(list(schema_map.get(t, set())))
                        for s in difflib.get_close_matches(base, candidates, n=5, cutoff=0.6):
                            suggestions.append(f"{m} -> {s}")
                if missing_columns:
                    suggest_for_missing(sorted(set(missing_columns)))
                if extra_missing:
                    # 仅列类错误参与建议
                    cols_only = [x.replace("列不存在: ", "") for x in extra_missing if x.startswith("列不存在")]
                    suggest_for_missing(sorted(set(cols_only)))
                on_options = []
                st = list(sorted(selected_tables))
                if len(st) >= 2:
                    pairs = []
                    for j in range(1, len(st)):
                        pairs.append((st[0], st[j]))
                    for a, b in pairs:
                        try:
                            cands = infer_join_candidates(a, b, searcher._get_schema(), top_k=5)
                            for on, score in cands:
                                on_options.append(on)
                        except Exception as _:
                            pass
                question = "检测到 DSL 引用了不存在的表/列或无效 JOIN，请选择正确的字段："
                payload = {
                    "status":"AMBIGUOUS",
                    "question": question,
                    "options": (options[:20] + on_options[:10]),
                    "type":"multiple",
                    "suggestions": suggestions[:10]
                }
                json_content = json.dumps(payload, ensure_ascii=False)
                return {
                    "intent_clear": False,
                    "messages": [AIMessage(content=json_content)]
                }
        except Exception as e:
            print(f"DEBUG: Precheck failed with exception: {e}")
            # 预检异常不阻断，进入编译
            pass
        # 3.2 编译 SQL
        compiler = DSLCompiler(dialect=db_type)
        try:
            sql = compiler.compile(dsl_json)
            print(f"DEBUG: Compiled SQL: {sql}")
        except Exception as e:
            print(f"Error compiling SQL: {e}")
            raise ValueError(f"DSL Compilation Failed: {e}")

        return {"sql": sql}
        
    except Exception as e:
        print(f"ERROR in dsl_to_sql_node: {e}")
        return {"intent_clear": False}
