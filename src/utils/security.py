import re

def is_safe_sql(sql: str) -> bool:
    """
    Check if the SQL string contains forbidden DDL/DML keywords.
    """
    if not sql:
        return False
        
    # Normalize SQL: remove newlines, convert to upper case
    normalized_sql = sql.upper().replace("\n", " ").strip()
    
    # 1. Whitelist Check: Must start with a read-only keyword
    allowed_starts = ["SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN", "VALUES"]
    if not any(normalized_sql.startswith(start) for start in allowed_starts):
        return False

    # 2. Blacklist Check: Forbidden keywords that indicate write operations or dangerous actions
    # We use word boundaries \b to avoid matching substrings (e.g., "SELECT_UPDATE")
    forbidden_patterns = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bUPDATE\b",
        r"\bINSERT\b",
        r"\bALTER\b",
        r"\bTRUNCATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bLOCK\b",
        r"\bCREATE\b",
        r"\bREPLACE\b",
        r"\bMERGE\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r"\bPRAGMA\b",
        r"\bSET\b", # Prevent variable changes
        r"\bCOMMIT\b",
        r"\bROLLBACK\b"
    ]
    
    for pattern in forbidden_patterns:
        if re.search(pattern, normalized_sql):
            return False
            
    # 3. Multi-statement Check: Prevent "SELECT ...; DROP ..."
    # Allow semicolons only if they are at the very end or followed only by comments/whitespace
    # Simple heuristic: Split by semicolon, ensure only one substantive statement
    statements = [s.strip() for s in normalized_sql.split(';') if s.strip()]
    if len(statements) > 1:
        return False
            
    return True
