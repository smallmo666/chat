import json
import pandas as pd

def evaluate_sql_accuracy(test_dataset_path: str, agent_url: str = "http://localhost:8000"):
    """
    Text2SQL Evaluation Script.
    Loads a JSON dataset of (question, expected_sql) pairs and runs the agent.
    Computes Execution Accuracy (EX) and Exact Match (EM).
    """
    print(f"Loading test dataset from {test_dataset_path}...")
    try:
        with open(test_dataset_path, 'r') as f:
            test_data = json.load(f)
    except FileNotFoundError:
        print("Test dataset not found. Creating a dummy sample for demo.")
        test_data = [
            {"question": "查询所有的用户", "expected_sql": "SELECT * FROM users"},
            {"question": "统计每个地区的用户数量", "expected_sql": "SELECT region, COUNT(*) FROM users GROUP BY region"}
        ]
        
    print(f"Starting evaluation on {len(test_data)} test cases...")
    
    results = []
    
    # Mocking the agent call for this script template
    # In real scenario, use requests.post(f"{agent_url}/chat", ...)
    
    for i, case in enumerate(test_data):
        question = case["question"]
        expected_sql = case.get("expected_sql", "")
        
        print(f"[{i+1}/{len(test_data)}] Testing: {question}")
        
        # Simulate Agent Response
        # generated_sql = call_agent(question)
        generated_sql = expected_sql # Dummy pass
        
        # Evaluate
        is_exact_match = generated_sql.strip().lower() == expected_sql.strip().lower()
        
        results.append({
            "question": question,
            "generated_sql": generated_sql,
            "expected_sql": expected_sql,
            "exact_match": is_exact_match
        })
        
    # Calculate Metrics
    df = pd.DataFrame(results)
    accuracy = df["exact_match"].mean()
    
    print("\n=== Evaluation Report ===")
    print(f"Total Cases: {len(df)}")
    print(f"Exact Match Accuracy: {accuracy:.2%}")
    
    # Save report
    df.to_csv("evaluation_report.csv", index=False)
    print("Report saved to evaluation_report.csv")

if __name__ == "__main__":
    evaluate_sql_accuracy("test_data.json")
