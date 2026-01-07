import re

def strip_db(sql: str, db: str) -> str:
    patterns = [
        rf'\b{re.escape(db)}\.',
        rf'"{re.escape(db)}"\.',
        rf'`{re.escape(db)}`\.',
    ]
    for p in patterns:
        sql = re.sub(p, '', sql)
    return sql

def test_strip_plain():
    sql = "SELECT * FROM cybermarket_pattern.transaction_products"
    assert "cybermarket_pattern." not in strip_db(sql, "cybermarket_pattern")

def test_strip_pg_quoted():
    sql = 'SELECT * FROM "cybermarket_pattern"."transaction_products"'
    out = strip_db(sql, "cybermarket_pattern")
    assert out == 'SELECT * FROM "transaction_products"'

def test_strip_mysql_backtick():
    sql = "SELECT * FROM `cybermarket_pattern`.`transaction_products`"
    out = strip_db(sql, "cybermarket_pattern")
    assert out == "SELECT * FROM `transaction_products`"
