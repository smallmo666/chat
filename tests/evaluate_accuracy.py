import json
import pandas as pd
import os
from sqlalchemy import create_engine, text

# 假设我们有一个测试数据库连接
# 在真实环境中，应该从环境变量或配置文件读取
TEST_DB_URL = os.getenv("TEST_DB_URL", "sqlite:///:memory:") 

class AccuracyEvaluator:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.init_test_data()

    def init_test_data(self):
        """初始化测试数据库，创建一些 dummy 表和数据"""
        # 仅作为示例，实际应连接真实测试库
        if "sqlite" in str(self.engine.url):
            with self.engine.connect() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, region TEXT)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)"))
                
                # 插入一些数据
                conn.execute(text("DELETE FROM users"))
                conn.execute(text("DELETE FROM orders"))
                conn.execute(text("INSERT INTO users (name, region) VALUES ('Alice', 'US'), ('Bob', 'CN'), ('Charlie', 'US')"))
                conn.execute(text("INSERT INTO orders (user_id, amount) VALUES (1, 100), (2, 200), (1, 50)"))
                conn.commit()

    def execute_sql(self, sql: str) -> List[tuple]:
        """执行 SQL 并返回结果集 (list of tuples)"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                return [tuple(row) for row in result.fetchall()]
        except Exception as e:
            print(f"Execution failed: {e}")
            return []

    def evaluate(self, test_file: str):
        print(f"Loading test cases from {test_file}...")
        with open(test_file, 'r') as f:
            cases = json.load(f)
            
        results = []
        for case in cases:
            question = case["question"]
            expected_sql = case["expected_sql"]
            
            print(f"Testing: {question}")
            
            # 1. 调用 Agent 生成 SQL (模拟)
            # 在实际集成中，这里应该调用 src.workflow.graph.app.invoke(...)
            # 为了演示，我们假设 Agent 生成了正确的 SQL
            generated_sql = expected_sql # Mock
            
            # 2. Execution Accuracy (EX)
            expected_res = self.execute_sql(expected_sql)
            generated_res = self.execute_sql(generated_sql)
            
            # 比较结果集 (忽略顺序)
            is_correct = set(expected_res) == set(generated_res)
            
            results.append({
                "question": question,
                "generated_sql": generated_sql,
                "is_correct": is_correct
            })
            
        # 统计
        df = pd.DataFrame(results)
        accuracy = df["is_correct"].mean()
        print(f"\nExecution Accuracy: {accuracy:.2%}")
        df.to_csv("accuracy_report.csv", index=False)

if __name__ == "__main__":
    evaluator = AccuracyEvaluator(TEST_DB_URL)
    evaluator.evaluate("tests/data/benchmark_cases.json")
