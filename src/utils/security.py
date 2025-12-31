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
        exp.Values, # VALUES (1,2)
        exp.Describe, # Allow DESCRIBE
        exp.Show # Allow SHOW
    )
    
    # Some dialects might parse SHOW/DESCRIBE differently, but standard SQL is Select.
    # We explicitly reject: Insert, Update, Delete, Drop, Create, Alter, etc.
    
    if not isinstance(statement, valid_types):
        # Check if it's a known DDL/DML/DCL
        # Explicitly block GRANT/REVOKE (DCL) and Transaction control if not needed
        forbidden_types = (
            exp.Insert, exp.Update, exp.Delete, 
            exp.Drop, exp.Create, exp.Alter, exp.Truncate, 
            exp.Command, # Often catch-all for unknown commands
            exp.Grant, exp.Revoke, exp.Commit, exp.Rollback
        )
        
        if isinstance(statement, forbidden_types):
            return False
            
        # Allow special "SHOW" or "DESCRIBE" if parsed as Command but safe text
        # But for now, sqlglot has types for them. 
        # If it's none of the above, be conservative.
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
