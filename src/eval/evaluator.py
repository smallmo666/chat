import asyncio
import json
import time
from typing import List, Dict, Any
from dataclasses import dataclass

from src.workflow.graph import create_graph
from src.core.database import get_query_db
from langchain_core.messages import HumanMessage

@dataclass
class EvalResult:
    id: int
    question: str
    generated_sql: str
    gold_sql: str
    exec_match: bool
    valid_sql: bool
    latency_ms: int
    error: str = None

class Evaluator:
    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self.graph = create_graph()
        # Use new get_query_db with project_id
        self.db = get_query_db(project_id)

    async def evaluate_dataset(self, dataset: List[Dict[str, Any]], parallel: int = 1) -> List[EvalResult]:
        """
        Run evaluation on a dataset.
        """
        semaphore = asyncio.Semaphore(parallel)
        results = []

        async def _process_item(item):
            async with semaphore:
                return await self.evaluate_single(item)

        tasks = [_process_item(item) for item in dataset]
        results = await asyncio.gather(*tasks)
        return results

    async def evaluate_single(self, item: Dict[str, Any]) -> EvalResult:
        """
        Evaluate a single item.
        """
        start_time = time.time()
        generated_sql = ""
        valid_sql = False
        exec_match = False
        error = None
        
        try:
            # 1. Run Agent
            inputs = {"messages": [HumanMessage(content=item["question"])]}
            config = {"configurable": {"thread_id": f"eval_{item['id']}", "project_id": self.project_id}}
            
            # Use ainvoke to run the full graph
            final_state = await self.graph.ainvoke(inputs, config=config)
            
            generated_sql = final_state.get("sql", "")
            
            if generated_sql:
                valid_sql = True
                
                # 2. Compare Execution Results
                # Execute Gold SQL
                gold_res = await self.db.run_query_async(item["gold_sql"])
                if gold_res.get("error"):
                    print(f"Gold SQL Error for ID {item['id']}: {gold_res['error']}")
                    # If Gold SQL fails, we can't judge execution match, assume False or Skip
                    exec_match = False
                else:
                    # Execute Generated SQL
                    gen_res = await self.db.run_query_async(generated_sql)
                    if gen_res.get("error"):
                        valid_sql = False # Exec failed means invalid logic usually
                    else:
                        # Compare Data
                        gold_data = json.loads(gold_res.get("json", "[]"))
                        gen_data = json.loads(gen_res.get("json", "[]"))
                        exec_match = self._compare_results(gold_data, gen_data)

        except Exception as e:
            error = str(e)
            print(f"Eval Error ID {item['id']}: {e}")

        latency = int((time.time() - start_time) * 1000)
        
        return EvalResult(
            id=item["id"],
            question=item["question"],
            generated_sql=generated_sql,
            gold_sql=item["gold_sql"],
            exec_match=exec_match,
            valid_sql=valid_sql,
            latency_ms=latency,
            error=error
        )

    def _compare_results(self, gold: List[Dict], gen: List[Dict]) -> bool:
        """
        Compare two result sets. 
        - Order independent for sets.
        - Tolerates extra columns in gen if they are just metadata (simplification).
        - Currently implements strict set equality on values.
        """
        if len(gold) != len(gen):
            return False
            
        # Convert list of dicts to set of frozensets for comparison (ignoring order)
        # This requires column names to match exactly or we compare values only.
        # Let's compare values only to be robust against alias differences (e.g. sum vs total).
        
        def _extract_values(rows):
            # Extract values, sort them to make a tuple, then add to set
            # This handles "SELECT a, b" vs "SELECT b, a" if we don't care about column mapping
            # But usually we do care. Let's assume standard SQL generation.
            # Simplified: Set of tuples of values.
            normalized = []
            for row in rows:
                # Sort keys to ensure consistent order if keys match
                # If keys don't match, we might have an issue.
                # Fallback: just values sorted by value representation
                vals = tuple(sorted([str(v) for v in row.values()]))
                normalized.append(vals)
            return set(normalized)

        return _extract_values(gold) == _extract_values(gen)
