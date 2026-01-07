import os, sys
sys.path.append(os.getcwd())
from src.core.dsl.compiler import DSLCompiler

def test_postgres_extract_cast():
    compiler = DSLCompiler(dialect="postgresql")
    dsl = {
        "command": "SELECT",
        "from": "reverse_logistics.orders",
        "columns": [
            {"name": "EXTRACT(YEAR FROM txndate)", "alias": "year"},
            {"name": "EXTRACT(MONTH FROM txndate)", "alias": "month"},
            {"name": "transaction_value", "agg": "SUM", "alias": "monthly_sales"},
        ],
        "group_by": ["year", "month"],
        "order_by": [{"column": "year", "direction": "ASC"}, {"column": "month", "direction": "ASC"}],
        "limit": 10,
    }
    sql = compiler.compile(dsl)
    assert "EXTRACT(YEAR FROM CAST(txndate AS DATE)) AS year" in sql
    assert "EXTRACT(MONTH FROM CAST(txndate AS DATE)) AS month" in sql
