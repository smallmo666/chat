import sqlglot
from sqlglot import exp

def is_safe_sql(sql: str) -> bool:
    """
    Check if the SQL string contains forbidden DDL/DML keywords using sqlglot parser.
    """
    if not sql:
        return False
        
    try:
        # Parse all statements in the SQL string
        parsed = sqlglot.parse(sql)
    except Exception as e:
        print(f"SQL Parsing Error: {e}")
        # If we can't parse it, it's safer to reject it (or fallback to regex, but rejection is safer)
        return False

    # Check for multiple statements
    if len(parsed) > 1:
        # Be strict: Only one statement allowed to prevent injection attacks
        return False
        
    statement = parsed[0]
    
    # 1. Root Node Check: Must be a read-only statement type
    # Allowed: SELECT, UNION (which is usually a binary expression of SELECTs)
    # Note: sqlglot parses "WITH ... SELECT" as a Select expression with a 'with' arg.
    
    valid_types = (
        exp.Select, 
        exp.Union, 
        exp.Subquery, 
        exp.Table, # rare as root
        exp.Values # VALUES (1,2)
    )
    
    # Some dialects might parse SHOW/DESCRIBE differently, but standard SQL is Select.
    # We explicitly reject: Insert, Update, Delete, Drop, Create, Alter, etc.
    
    if not isinstance(statement, valid_types):
        # Check if it's a known DDL/DML
        if isinstance(statement, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Truncate, exp.Command)):
            return False
        # Allow special "SHOW" or "DESCRIBE" if the dialect supports/parses them, 
        # but sqlglot often puts them in Command or specific types.
        # For safety, let's strictly allow only SELECT-like structures.
        return False

    # 2. Deep Traversal Check (Guardrails)
    # Ensure no dangerous functions or sub-clauses are hidden inside
    # e.g. "SELECT * FROM t WHERE 1=1; DROP TABLE t" (caught by len check above)
    # e.g. "SELECT pg_sleep(10)" (DoS prevention)
    
    for node in statement.walk():
        # Check for dangerous functions
        if isinstance(node, exp.Func):
            func_name = node.sql().upper()
            if "SLEEP" in func_name or "BENCHMARK" in func_name:
                return False
                
        # Double check for nested DML (unlikely in standard grammar but possible in some injections)
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)):
            return False

    return True
