import argparse
import asyncio
import json
import os
from tabulate import tabulate
from src.eval.evaluator import Evaluator

async def main():
    parser = argparse.ArgumentParser(description="Run Text2SQL Evaluation")
    parser.add_argument("--data", default="src/eval/data/golden_dataset.json", help="Path to golden dataset")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to eval")
    parser.add_argument("--parallel", type=int, default=3, help="Concurrency level")
    parser.add_argument("--project_id", type=int, default=None, help="Project ID context")
    
    args = parser.parse_args()
    
    # Load Data
    if not os.path.exists(args.data):
        print(f"Error: Dataset not found at {args.data}")
        return

    with open(args.data, "r") as f:
        dataset = json.load(f)
        
    if args.limit:
        dataset = dataset[:args.limit]
        
    print(f"🚀 Starting Evaluation on {len(dataset)} items (Parallel={args.parallel})...")
    
    evaluator = Evaluator(project_id=args.project_id)
    results = await evaluator.evaluate_dataset(dataset, parallel=args.parallel)
    
    # Report
    table_data = []
    total_exec_match = 0
    total_valid = 0
    total_latency = 0
    
    for res in results:
        status = "✅ PASS" if res.exec_match else "❌ FAIL"
        if not res.valid_sql:
            status = "⚠️ INVALID"
            
        table_data.append([
            res.id,
            res.question[:30] + "...",
            status,
            f"{res.latency_ms}ms",
            res.generated_sql[:30] + "..." if res.generated_sql else "N/A"
        ])
        
        if res.exec_match: total_exec_match += 1
        if res.valid_sql: total_valid += 1
        total_latency += res.latency_ms
        
    print("\n" + tabulate(table_data, headers=["ID", "Question", "Status", "Latency", "Generated SQL"]))
    
    # Summary
    avg_latency = total_latency / len(dataset) if dataset else 0
    accuracy = (total_exec_match / len(dataset)) * 100 if dataset else 0
    validity = (total_valid / len(dataset)) * 100 if dataset else 0
    
    print("\n📊 Evaluation Summary")
    print("=======================")
    print(f"Total Items: {len(dataset)}")
    print(f"Execution Accuracy: {accuracy:.1f}%")
    print(f"Valid SQL Rate:     {validity:.1f}%")
    print(f"Average Latency:    {avg_latency:.0f}ms")
    
    # Save detailed report
    report_path = "eval_report.json"
    with open(report_path, "w") as f:
        # Convert dataclass to dict
        report_data = [vars(r) for r in results]
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed report saved to {report_path}")

if __name__ == "__main__":
    asyncio.run(main())
