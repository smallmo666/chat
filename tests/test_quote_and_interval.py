import pytest
from src.workflow.nodes.dsl2sql import _quote_case_identifiers

def test_quotes_uppercase_column_in_function_and_cast():
    sql = "SELECT date_trunc('month', current_date - buyers.ProfileAge::interval) AS registration_month, COUNT(*) AS new_users_count FROM buyers WHERE buyers.ProfileAge <= 180 GROUP BY registration_month ORDER BY registration_month ASC"
    out = _quote_case_identifiers(sql)
    assert 'buyers."ProfileAge"' in out
    assert " * interval '1 day'" in out

def test_quotes_uppercase_in_aggregate():
    sql = "SELECT COUNT(buyers.ProfileAge) AS c FROM buyers"
    out = _quote_case_identifiers(sql)
    assert 'COUNT(buyers."ProfileAge")' in out
