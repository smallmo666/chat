I will enhance the user interface to stream the LLM's "thinking process" (tokens) in real-time, in addition to the plan steps.

### 1. Enable Streaming in Agents
I will update the agent nodes (`ClarifyIntent`, `GenerateDSL`, `DSLtoSQL`, `Supervisor`) to support streaming token output.
-   **Current**: They use `invoke()` which waits for the full response.
-   **New**: I will not change the nodes to stream directly (as LangGraph nodes usually return state updates), but I will add a **callback handler** or use LangChain's `astream_events` API in `main.py` to capture LLM generation events.
-   Actually, a simpler approach for LangGraph is to capture `on_chat_model_stream` events if we use `app.stream(..., stream_mode="events")` or similar.
-   However, since our nodes currently just call `invoke`, I will modify `main.py` to use a custom `CallbackHandler` passed to the graph invocation, or more robustly, I will modify the nodes to accept a `config` with callbacks, but that's complex.
-   **Better Strategy**: I will modify `main.py` to use `app.stream_events` (available in newer LangGraph/LangChain versions) which allows intercepting token generation events from the underlying LLM calls within the nodes.

### 2. UI Updates (`src/main.py`)
I will integrate a "Thinking" panel into the `rich` UI.
-   **Layout**: Split the view or add a collapsible/scrollable panel for "思考过程 (Thinking Process)".
-   **Streaming**: As tokens arrive (via `stream_events`), I will append them to this panel in real-time.
-   **Structure**:
    -   When a node starts (e.g., "GenerateDSL"), I'll show a header in the thinking panel.
    -   Stream the tokens.
    -   When finished, show the structured result (like the DSL JSON) in the main Plan table as before.

### 3. Implementation Details
-   **`src/main.py`**:
    -   Switch from `app.stream()` to `app.astream_events()` (requires `async` main loop) or use `app.stream(..., stream_mode="messages")` if supported. Given the current sync setup, `astream_events` is best, so I'll need to make `main()` async.
    -   Alternatively, I can pass a `StreamingStdOutCallbackHandler` or a custom Rich-based callback to the `llm` in the agents. But the `llm` object is global in agent files.
    -   **Refinement**: I will pass a custom callback handler via `config` in `app.stream`.
    -   I'll create a `RichStreamingHandler` that updates a `rich.Live` component.

### Plan
1.  **Create `src/utils/callbacks.py`**: A custom LangChain callback handler that updates a global/shared `rich` display context with token streams.
2.  **Update `src/agents/*.py`**: Ensure `llm.invoke` receives the `callbacks` from the `config` (LangChain usually propagates this automatically if using `chain.invoke(..., config=config)`). I need to ensure `config` is passed through.
3.  **Refactor `src/main.py`**:
    -   Initialize the `RichStreamingHandler`.
    -   Pass it in the `config` to `app.stream`.
    -   Update the layout to include a "Thinking" box that the handler writes to.

*Wait, `app.stream` in LangGraph might not propagate callbacks easily to inner chains unless configured perfectly. A simpler, more robust way for this demo:*
I will use `app.astream_events` in an `async` main loop. This provides granular events like `on_chat_model_stream` without modifying every agent file to handle callbacks manually.

**Revised Plan**:
1.  **Refactor `main.py` to be `async`**: Use `import asyncio` and `async def main()`.
2.  **Use `app.astream_events`**: Iterate over events.
    -   `on_chat_model_start`: Show "Agent is thinking..."
    -   `on_chat_model_stream`: Update the "Thinking" panel with new tokens.
    -   `on_chain_end` / node events: Update the Plan table status.
3.  **UI Layout**: Use `rich.layout` or a simple `Group` of `Panel` (Thinking) + `Table` (Plan).

This approach is non-intrusive to the agent logic and provides the best visual effect.