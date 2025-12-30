import json
import re
import asyncio
from typing import List, Dict
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.core.llm import get_llm
from src.workflow.nodes.gen_dsl import generate_dsl_node
from src.workflow.nodes.dsl2sql import dsl_to_sql_node
from src.workflow.state import AgentState
from langchain_core.messages import HumanMessage

async def evaluate():
    print("Starting Evaluation...")
    
    # Load Golden Dataset
    with open("tests/data/golden_dataset.json", "r") as f:
        dataset = json.load(f)
        
    results = []
    
    # Mock Config
    config = {"configurable": {"project_id": 1}} # Assuming project 1 exists
    
    for item in dataset:
        question = item["question"]
        expected_pattern = item["expected_sql_pattern"]
        
        print(f"\nEvaluating: {question}")
        
        # Mock State
        state = AgentState()
        state["messages"] = [HumanMessage(content=question)]
        state["relevant_schema"] = "users(id, name, email), products(id, name, price), orders(id, user_id, amount), order_items(order_id, product_id, quantity)" # Mock Schema
        
        try:
            # 1. Generate DSL
            dsl_result = generate_dsl_node(state, config)
            state["dsl"] = dsl_result.get("dsl")
            
            # 2. DSL to SQL
            if state.get("dsl"):
                sql_result = dsl_to_sql_node(state, config)
                generated_sql = sql_result.get("sql", "").strip()
            else:
                generated_sql = ""
                
            # 3. Compare
            match = re.search(expected_pattern, generated_sql, re.IGNORECASE)
            is_pass = bool(match)
            
            print(f"  Generated SQL: {generated_sql}")
            print(f"  Expected Pattern: {expected_pattern}")
            print(f"  Result: {'PASS' if is_pass else 'FAIL'}")
            
            results.append({
                "question": question,
                "pass": is_pass,
                "generated": generated_sql,
                "expected": expected_pattern
            })
            
        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                "question": question,
                "pass": False,
                "error": str(e)
            })

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    accuracy = (passed / total) * 100 if total > 0 else 0
    
    print("\n" + "="*30)
    print(f"Evaluation Complete")
    print(f"Total: {total}, Passed: {passed}, Accuracy: {accuracy:.2f}%")
    print("="*30)

if __name__ == "__main__":
    asyncio.run(evaluate())
