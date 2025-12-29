# Implementation Plan: SQL Retry Mechanism & Security Enhancements

I will implement a robust retry mechanism for SQL execution failures and add a security layer to prevent dangerous SQL operations.

## 1. State Management Update
**File:** [`src/state/state.py`](src/state/state.py)
- Update `AgentState` definition to include:
    - `error`: `Optional[str]` - To store the latest error message.
    - `retry_count`: `int` - To track the number of retry attempts (default 0).

## 2. Security & Error Handling in ExecuteSQL
**File:** [`src/agents/execute.py`](src/agents/execute.py)
- **Security Check**:
    - Implement `is_safe_sql(sql: str) -> bool` helper function.
    - Use Regex to strictly forbid DDL/DML keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`) to ensure read-only access.
    - Raise a specific `ValueError` if unsafe keywords are detected.
- **Error Capture**:
    - Wrap the database execution logic in a `try...except` block.
    - **On Failure**: 
        - Capture the exception message.
        - Return `{"error": str(e), "results": "Execution Failed"}` to the state.
        - Do **not** throw the exception up to the graph runner (which would crash the app).
    - **On Success**:
        - Return `{"error": None, "retry_count": 0, ...}` to clear any previous error state.

## 3. Intelligent Retry Routing (Supervisor)
**File:** [`src/agents/supervisor.py`](src/agents/supervisor.py)
- Modify the `supervisor_node` logic to act as a smart router:
    - **Check for Errors**: Before scheduling the next step, check if `state["error"]` is present.
    - **Retry Logic**:
        - If an error exists and `retry_count < 3`:
            - Identify the index of the **`GenerateDSL`** node in the current plan.
            - **Rewind**: Set `current_step_index` back to the `GenerateDSL` step.
            - Increment `retry_count`.
            - Return `{"next": "GenerateDSL", ...}` to trigger the retry loop.
        - If `retry_count >= 3`:
            - Treat as a hard failure and proceed to the next step (likely `DataAnalysis`, which will handle the empty/error result) or end the flow.

## 4. Context-Aware DSL Generation
**File:** [`src/agents/gen_dsl.py`](src/agents/gen_dsl.py)
- Update the prompt construction to check for `state["error"]`.
- If an error exists (indicating a retry), append a **System Hint**: 
    > "Previous attempt failed with error: {error}. Please fix the logic/column names."
- This ensures the Agent actually learns from the mistake instead of repeating it.

## Verification Plan
- **Security Test**: Try to execute `DROP TABLE users;` via the chat interface and verify it is blocked.
- **Retry Test**: 
    - Query with a non-existent column to trigger a SQL error.
    - Observe the logs/UI to confirm the system loops back to `GenerateDSL` and retries.
