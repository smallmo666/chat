I will upgrade the agent to support interactive clarification and state persistence (Human-in-the-Loop).

### 1. Enable State Persistence (`src/graph.py`)
I will introduce `MemorySaver` to the graph. This allows the agent to "remember" the conversation context and resume execution after getting user input.

### 2. Upgrade `ClarifyIntent` Node (`src/agents/clarify.py`)
I will replace the keyword heuristic with a real LLM call:
-   **Analyze**: Check if the user's request is complete enough for SQL generation.
-   **Action**:
    -   If **Clear**: Mark `intent_clear=True`.
    -   If **Ambiguous**: Generate a specific clarifying question (e.g., "Do you want to filter by a specific year?") and mark `intent_clear=False`.

### 3. Update Supervisor Logic (`src/agents/supervisor.py`)
I will adjust the routing logic to support the interactive loop:
-   If `intent_clear` is `False` and the **last message is from the AI** (meaning we just asked a question), route to `FINISH`. This effectively "interrupts" the autonomous execution to wait for the user.
-   If `intent_clear` is `False` but the **last message is from the Human** (user just replied), route back to `ClarifyIntent` to re-evaluate.

### 4. Interactive CLI (`src/main.py`)
I will refactor `main.py` into a continuous chat loop:
-   Initialize a `thread_id` for the session.
-   Loop:
    1.  Get user input.
    2.  Run the graph with the current config.
    3.  Display agent output.
    4.  If the agent asks a question (pauses), the loop continues and waits for the user's next answer.

This approach fulfills the requirement: The agent detects ambiguity -> Interrupts/Pauses -> User clarifies -> Agent re-executes/Resumes.