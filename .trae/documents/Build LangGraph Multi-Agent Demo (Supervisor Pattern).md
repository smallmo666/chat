I will build a Multi-Agent system using LangGraph demonstrating the **Supervisor Pattern**. This pattern involves a supervisor agent that routes tasks to specialized worker agents and coordinates their responses.

### 1. Project Dependencies
I will add the necessary dependencies for LangGraph and OpenAI integration:
- `langchain-openai`: For the LLM (assuming OpenAI).
- `langchain-community`: For standard tools.
- `duckduckgo-search`: For a free web search tool (so the "Researcher" agent works out-of-the-box).

### 2. Implementation in `src/lg.py`
I will implement the following components:

#### A. State Definition
- Define `AgentState` containing the conversation history (`messages`) and the `next` agent to call.

#### B. Worker Agents
- **Researcher**: Equipped with `DuckDuckGo` search to find information.
- **Chart Generator / Coder**: Equipped with a Python REPL (or a mock coding tool) to execute calculations or generate code snippets.
- *Helper Function*: A `create_agent` utility to easily build these worker nodes.

#### C. Supervisor Agent
- An LLM node that analyzes the current state and decides:
  - Which worker to route to next (`Researcher` or `Coder`).
  - Or if the task is `FINISH`.

#### D. The Graph
- Construct a `StateGraph`.
- Add nodes for the Supervisor and Workers.
- Add conditional edges from the Supervisor to Workers based on the routing decision.
- Add normal edges from Workers back to the Supervisor.

### 3. Execution Demo
- I will add a `__main__` block to `src/lg.py` that runs a sample query (e.g., "Research the performance of the S&P 500 over the last 5 years and calculate the average yearly return") to demonstrate the agents collaborating.
