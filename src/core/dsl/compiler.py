from sqlalchemy import select, table, func, text, desc, asc, literal_column
from sqlalchemy.dialects import mysql, postgresql

class DSLCompiler:
    """
    将 JSON DSL 编译为 SQLAlchemy 表达式，并生成目标方言的 SQL 字符串。
    支持 Dialect: 'mysql', 'postgresql'
    """
    def __init__(self, dialect: str = 'mysql'):
        self.dialect = dialect.lower()
        
    def compile(self, dsl_json: dict) -> str:
        """
        核心编译方法
        dsl_json: 
        {
          "command": "SELECT",
          "from": "orders",
          "joins": [...],
          "columns": [{"name": "id", "table": "orders"}, ...],
          "where": {"logic": "AND", "conditions": [...]},
          "group_by": [...],
          "order_by": [...],
          "limit": 10
        }
        """
        # 1. 基础表 (FROM)
        main_table_name = dsl_json.get("from")
        if not main_table_name:
            raise ValueError("DSL missing 'from' table")
            
        # 使用 text() 来处理表名，以便支持 schema.table 格式 (SQLAlchemy table() 有时处理 schema 比较麻烦，这里简化处理)
        # 或者我们解析 schema.table
        main_table = self._get_table_obj(main_table_name)
        stmt = select() # 初始化 select
        
        # 我们构建一个 selectable 对象，初始为 main_table
        selectable = main_table
        
        # 2. Joins
        if "joins" in dsl_json:
            for join_info in dsl_json["joins"]:
                join_table_name = join_info["table"]
                join_table = self._get_table_obj(join_table_name)
                
                # Join Type
                is_outer = join_info.get("type", "INNER").upper() == "LEFT"
                
                # On Condition (String literal for now, parsing complex ON is hard)
                # 假设 DSL 中的 ON 是字符串 "orders.user_id = users.id"
                on_clause = text(join_info["on"])
                
                selectable = selectable.join(join_table, on_clause, isouter=is_outer)
        
        # 3. Columns (SELECT)
        cols = []
        if "columns" in dsl_json and dsl_json["columns"]:
            for col_def in dsl_json["columns"]:
                # col_def: {name, table, agg, alias}
                c_name = col_def["name"]
                t_name = col_def.get("table")
                
                # 如果指定了表名，加前缀；否则假设唯一或已经在 where 处理
                # 使用 literal_column 处理 "table.col" 格式最稳妥
                full_name = f"{t_name}.{c_name}" if t_name else c_name
                c_obj = literal_column(full_name)
                
                # Aggregation
                agg = col_def.get("agg")
                if agg:
                    agg = agg.upper()
                    if agg == "SUM":
                        c_obj = func.sum(c_obj)
                    elif agg == "COUNT":
                        c_obj = func.count(c_obj)
                    elif agg == "AVG":
                        c_obj = func.avg(c_obj)
                    elif agg == "MAX":
                        c_obj = func.max(c_obj)
                    elif agg == "MIN":
                        c_obj = func.min(c_obj)
                
                # Alias
                alias = col_def.get("alias")
                if alias:
                    c_obj = c_obj.label(alias)
                    
                cols.append(c_obj)
        else:
            cols.append(text("*"))
            
        stmt = select(*cols).select_from(selectable)
        
        # 4. Where
        if "where" in dsl_json and dsl_json["where"]:
            where_clause = self._parse_where(dsl_json["where"])
            if where_clause is not None:
                stmt = stmt.where(where_clause)
                
        # 5. Group By
        if "group_by" in dsl_json and dsl_json["group_by"]:
            groups = []
            for g in dsl_json["group_by"]:
                groups.append(text(g))
            stmt = stmt.group_by(*groups)
            
        # 6. Having (New Feature)
        if "having" in dsl_json and dsl_json["having"]:
            having_clause = self._parse_where(dsl_json["having"]) # Reuse where parser
            if having_clause is not None:
                stmt = stmt.having(having_clause)

        # 7. Distinct (New Feature)
        if dsl_json.get("distinct", False):
            stmt = stmt.distinct()

        # 8. Order By
        if "order_by" in dsl_json and dsl_json["order_by"]:
            orders = []
            for o in dsl_json["order_by"]:
                col = text(o["column"])
                direction = o.get("direction", "ASC").upper()
                if direction == "DESC":
                    orders.append(desc(col))
                else:
                    orders.append(asc(col))
            stmt = stmt.order_by(*orders)
            
        # 9. Limit
        if "limit" in dsl_json:
            stmt = stmt.limit(int(dsl_json["limit"]))
            
        # Compile to String
        compile_kwargs = {"literal_binds": True}
        if self.dialect == 'postgresql':
            compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs=compile_kwargs)
        else:
            compiled = stmt.compile(dialect=mysql.dialect(), compile_kwargs=compile_kwargs)
            
        return str(compiled)

    def _get_table_obj(self, table_name):
        # 处理 schema.table
        if "." in table_name:
            schema, name = table_name.split(".", 1)
            return table(name, schema=schema)
        return table(table_name)

    def _parse_where(self, where_def):
        """
        递归解析 WHERE/HAVING 条件
        """
        if not where_def:
            return None
            
        logic = where_def.get("logic", "AND").upper()
        conditions = where_def.get("conditions", [])
        
        parsed_conds = []
        for cond in conditions:
            if "logic" in cond:
                # Nested
                nested = self._parse_where(cond)
                if nested is not None:
                    parsed_conds.append(nested)
            else:
                # Leaf condition
                col_name = cond["column"]
                op = cond["op"].upper()
                val = cond["value"]
                
                # --- Smart LIKE Handling ---
                if "LIKE" in op:
                    if isinstance(val, str) and "%" not in val:
                        # 默认两端模糊匹配
                        val = f"%{val}%"
                # ---------------------------

                # Handle types (simple)
                if isinstance(val, str):
                    # Escape single quotes to prevent injection in literal usage
                    safe_val = val.replace("'", "''")
                    val_str = f"'{safe_val}'"
                else:
                    val_str = str(val)
                
                expr = text(f"{col_name} {op} {val_str}")
                parsed_conds.append(expr)
        
        if not parsed_conds:
            return None
            
        if logic == "OR":
            from sqlalchemy import or_
            return or_(*parsed_conds)
        else:
            from sqlalchemy import and_
            return and_(*parsed_conds)
