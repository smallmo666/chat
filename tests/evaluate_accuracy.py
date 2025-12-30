import sys
import os
import json
import asyncio
import pandas as pd
from sqlalchemy import text
from termcolor import colored

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.db import get_query_db
from src.state.state import AgentState
from src.agents.gen_dsl import generate_dsl_node
from src.agents.dsl2sql import dsl_to_sql_node
from langchain_core.messages import HumanMessage

class BenchmarkRunner:
    def __init__(self, cases_path: str = "tests/data/benchmark_cases.json"):
        self.cases_path = cases_path
        with open(cases_path, "r") as f:
            self.cases = json.load(f)
        self.db = get_query_db()
        self.results = []

    async def run_query_on_db(self, sql: str):
        try:
            # 使用同步方法，因为 evaluate 脚本通常不是 async 链的一环，简单起见
            # 但 QueryDatabase 现在支持 async。我们这里使用 run_query (sync wrapper) 方便对比
            # 或者使用 async run_query_async
            res = await self.db.run_query_async(sql)
            if res.get("error"):
                return None, res["error"]
            # 解析 JSON 结果
            data = json.loads(res["json"])
            return data, None
        except Exception as e:
            return None, str(e)

    def compare_results(self, res1, res2) -> bool:
        """
        比较两个结果集是否一致 (忽略顺序)。
        """
        if res1 is None or res2 is None:
            return False
        
        # 简单比较：转换为 DataFrame 然后排序比较
        try:
            df1 = pd.DataFrame(res1)
            df2 = pd.DataFrame(res2)
            
            if df1.empty and df2.empty:
                return True
            if df1.shape != df2.shape:
                return False
                
            # 统一列名大小写?
            # 排序
            df1_sorted = df1.sort_values(by=list(df1.columns)).reset_index(drop=True)
            df2_sorted = df2.sort_values(by=list(df2.columns)).reset_index(drop=True)
            
            return df1_sorted.equals(df2_sorted)
        except Exception:
            return False

    async def run(self):
        print(colored(f"🚀 Starting Benchmark: {len(self.cases)} cases", "cyan", attrs=["bold"]))
        
        passed = 0
        
        for i, case in enumerate(self.cases):
            q = case["question"]
            expected_sql = case["expected_sql"]
            print(f"\n[{i+1}/{len(self.cases)}] Testing: {q}")
            
            # 1. Generate SQL (Simulation)
            # 我们模拟 Graph 的一部分：GenerateDSL -> DSLtoSQL
            state = AgentState(messages=[HumanMessage(content=q)])
            
            # Mock config
            config = {"configurable": {"project_id": 1}} # Assuming project 1
            
            try:
                # Step 1: Gen DSL
                state_dsl = generate_dsl_node(state, config)
                dsl = state_dsl.get("dsl")
                state["dsl"] = dsl
                
                # Step 2: DSL to SQL
                state_sql = dsl_to_sql_node(state, config)
                generated_sql = state_sql.get("sql")
                
                print(f"   Generated SQL: {generated_sql}")
                
                # 2. Execute Both
                print("   Executing Expected SQL...")
                expected_res, err1 = await self.run_query_on_db(expected_sql)
                if err1:
                    print(colored(f"   ⚠️ Expected SQL Failed: {err1}", "yellow"))
                    # 如果标准答案都跑不通，可能是环境问题，跳过
                    continue

                print("   Executing Generated SQL...")
                gen_res, err2 = await self.run_query_on_db(generated_sql)
                
                if err2:
                    print(colored(f"   ❌ Execution Failed: {err2}", "red"))
                    self.results.append({"case": q, "status": "exec_error", "error": err2})
                    continue
                
                # 3. Compare
                is_match = self.compare_results(expected_res, gen_res)
                
                if is_match:
                    print(colored("   ✅ PASS", "green"))
                    passed += 1
                    self.results.append({"case": q, "status": "pass"})
                else:
                    print(colored("   ❌ FAIL (Result Mismatch)", "red"))
                    print(f"   Expected: {len(expected_res)} rows, Got: {len(gen_res)} rows")
                    self.results.append({"case": q, "status": "mismatch", "generated_sql": generated_sql})

            except Exception as e:
                print(colored(f"   ❌ System Error: {e}", "red"))
                self.results.append({"case": q, "status": "system_error", "error": str(e)})

        accuracy = (passed / len(self.cases)) * 100
        print(colored(f"\n📊 Benchmark Finished. Accuracy: {accuracy:.2f}% ({passed}/{len(self.cases)})", "cyan", attrs=["bold"]))

if __name__ == "__main__":
    runner = BenchmarkRunner()
    asyncio.run(runner.run())
