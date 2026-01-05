import sqlglot
from sqlglot import exp

def is_safe_sql(sql: str) -> bool:
    """
    使用 sqlglot 解析器检查 SQL 字符串是否包含被禁止的 DDL/DML 关键字。
    """
    if not sql:
        return False
        
    try:
        # 解析 SQL 字符串中的所有语句
        parsed = sqlglot.parse(sql)
    except Exception as e:
        print(f"SQL 解析错误: {e}")
        # 如果无法解析，为安全起见直接拒绝（也可以回退到正则，但拒绝更安全）
        return False

    # 检查是否包含多条语句
    if len(parsed) > 1:
        # 严格模式：仅允许单条语句，以防止注入攻击
        return False
        
    statement = parsed[0]
    
    # 1. 根节点检查：必须是只读语句类型
    # 允许：SELECT, UNION (通常是 SELECT 的二元表达式)
    # 注意：sqlglot 将 "WITH ... SELECT" 解析为带有 'with' 参数的 Select 表达式。
    
    valid_types = (
        exp.Select, 
        exp.Union, 
        exp.Subquery, 
        exp.Table, # 极少作为根节点
        exp.Values, # VALUES (1,2)
        exp.Describe, # 允许 DESCRIBE
        exp.Show # 允许 SHOW
    )
    
    # 某些方言可能对 SHOW/DESCRIBE 解析不同，但标准 SQL 是 Select。
    # 我们明确拒绝：Insert, Update, Delete, Drop, Create, Alter 等。
    
    if not isinstance(statement, valid_types):
        # 检查是否为已知的 DDL/DML/DCL
        # 明确阻止 GRANT/REVOKE (DCL) 和不需要的事务控制
        forbidden_types = (
            exp.Insert, exp.Update, exp.Delete, 
            exp.Drop, exp.Create, exp.Alter, exp.TruncateTable, 
            exp.Command, # 通常是未知命令的捕获
            exp.Grant, exp.Revoke, exp.Commit, exp.Rollback
        )
        
        if isinstance(statement, forbidden_types):
            return False
            
        # 允许特殊的 "SHOW" 或 "DESCRIBE"（如果被解析为 Command 但文本安全）
        # 但目前 sqlglot 有专门的类型。
        # 如果都不匹配，保持保守策略。
        return False

    # 2. 深度遍历检查 (Guardrails)
    # 确保内部没有隐藏危险函数或子句
    # 例如 "SELECT * FROM t WHERE 1=1; DROP TABLE t" (已被上面的长度检查捕获)
    # 例如 "SELECT pg_sleep(10)" (DoS 攻击防御)
    
    for node in statement.walk():
        # 检查危险函数
        if isinstance(node, exp.Func):
            func_name = node.sql().upper()
            if "SLEEP" in func_name or "BENCHMARK" in func_name:
                return False
                
        # 双重检查嵌套的 DML（在标准语法中不太可能，但在某些注入中可能存在）
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)):
            return False

    return True
