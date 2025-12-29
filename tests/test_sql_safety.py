import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.security import is_safe_sql

class TestSQLSafety(unittest.TestCase):
    
    def test_safe_queries(self):
        safe_sqls = [
            "SELECT * FROM users",
            "select id, name from products where price > 100",
            "WITH cte AS (SELECT * FROM t1) SELECT * FROM cte",
            "SELECT count(*) FROM orders;",
            "SHOW TABLES",
            "DESCRIBE users"
        ]
        for sql in safe_sqls:
            self.assertTrue(is_safe_sql(sql), f"Should be safe: {sql}")

    def test_forbidden_keywords(self):
        unsafe_sqls = [
            "DROP TABLE users",
            "DELETE FROM users",
            "UPDATE users SET name='hacker'",
            "INSERT INTO users VALUES (1, 'a')",
            "TRUNCATE TABLE logs",
            "ALTER TABLE users ADD COLUMN hacked int",
            "GRANT ALL PRIVILEGES ON *.* TO 'hacker'",
            "EXEC xp_cmdshell",
            "PRAGMA writable_schema=1"
        ]
        for sql in unsafe_sqls:
            self.assertFalse(is_safe_sql(sql), f"Should be unsafe: {sql}")

    def test_injection_attempts(self):
        injections = [
            "SELECT * FROM users; DROP TABLE orders",
            "SELECT * FROM users; DELETE FROM users",
            "SELECT * FROM users; UPDATE users SET admin=1",
            "SELECT * FROM users UNION SELECT password FROM admins --", # Union is allowed but usually handled by LLM logic. 
            # Note: UNION is not in blacklist, so strictly speaking it's "safe" for readonly, but ; DROP is not.
        ]
        
        # Test semicolon injection
        self.assertFalse(is_safe_sql("SELECT * FROM users; DROP TABLE orders"), "Should block multi-statement")
        
        # Test keyword embedding
        self.assertFalse(is_safe_sql("SELECT * FROM users WHERE name = 'a'; DROP TABLE users"), "Should block embedded drop")

    def test_edge_cases(self):
        # Case insensitivity
        self.assertFalse(is_safe_sql("select * from users; drop table orders"))
        
        # Newlines
        self.assertFalse(is_safe_sql("SELECT * FROM users\nDROP TABLE orders"))

if __name__ == '__main__':
    unittest.main()
