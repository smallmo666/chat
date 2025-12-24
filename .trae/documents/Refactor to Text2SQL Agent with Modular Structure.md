I will restructure the project into a modular, professional Text2SQL agent system.

### 1. Project Structure Refactoring
I will create a new `src` structure to separate concerns, with each node in its own file:

```text
src/
├── agents/             # Agent Node Definitions
│   ├── __init__.py
│   ├── supervisor.py   # Routing logic
│   ├── clarify.py      # Clarify Intent Node
│   ├── gen_dsl.py      # Generate DSL Node
│   ├── dsl2sql.py      # DSL to SQL Node
│   └── execute.py      # Execute SQL Node
├── state/              # State Management
│   └── state.py        # AgentState definition
├── utils/              # Utilities
│   ├── llm.py          # LLM initialization
│   └── db.py           # Database mock/setup
├── graph.py            # Main Graph Construction
└── main.py             # Entry point
```

### 2. Implementation Details

#### A. State Definition (`src/state/state.py`)
Extend `AgentState` to track the pipeline progress:
- `dsl`: The intermediate Domain Specific Language representation.
- `sql`: The generated SQL query.
- `results`: The execution results.
- `intent_clear`: Boolean flag (optional, or inferred).

#### B. Nodes (`src/agents/`)
1.  **Supervisor**: Analyzes state to route to the next logical step (Clarify -> DSL -> SQL -> Execute -> Finish).
2.  **Clarify Intent**: If the request is ambiguous (e.g., "Show me data"), asks for specifics.
3.  **Generate DSL**: Converts natural language to a structured JSON DSL (e.g., `{"entity": "users", "filters": [...]}`).
4.  **DSL to SQL**: Converts the JSON DSL to a valid SQL string.
5.  **Execute SQL**: Runs the SQL against a dummy SQLite database (which I will seed with some sample data).

#### C. Graph Construction (`src/graph.py`)
- Import all nodes.
- Define the `StateGraph`.
- Register the Supervisor as the entry point and the central router.

### 3. Execution
- Update `main.py` (or the entry point) to run this new graph.
- I will verify the flow by asking a query like "Find all users who joined in 2023".

I will delete the old `src/lg.py` after the new structure is confirmed working to keep the workspace clean.