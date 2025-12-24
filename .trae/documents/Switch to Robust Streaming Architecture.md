### Analysis
The `debug_graph.py` run confirms that the **Core Logic is working perfectly**.
-   Supervisor routes correctly.
-   Agents (Clarify, DSL, SQL, Execute) all perform their tasks.
-   Database connections are successful.
-   Even the `mem0` embedding error (404 model not found) is handled gracefully in `ClarifyIntent` (it just logs "搜索记忆失败" and proceeds).

**Conclusion**: The issue is strictly in the **UI / Streaming Layer** (`src/main.py`).

### Hypothesis for UI Failure
1.  **`astream_events` Silence**: The `debug_graph.py` used `app.stream()`. The UI uses `app.astream_events()`. It's possible that `astream_events` is throwing an error internally (perhaps related to the Pydantic v1 warnings or serialization of events) which I suppressed with `pass`, causing the loop to terminate early or hang.
2.  **Live Update Conflict**: `rich.Live` might not be refreshing if the async loop gets blocked or if exceptions break the context manager.

### Strategy
Since `app.stream()` works reliably (proven by `debug_graph.py`), but `app.astream_events()` is causing trouble (likely due to complex event serialization with the Pydantic v1 models used by Supervisor), I will switch `src/main.py` back to using `app.stream()`.

**But how to get streaming tokens?**
If I use `app.stream()`, I lose the granular `on_chat_model_stream` events needed for the "Thinking" effect.
**Alternative**: I can inject a **callback handler** into the `config` passed to `app.stream()`.
LangChain allows passing callbacks via `config={"callbacks": [MyCustomCallback()]}`.
This callback can update a shared state (e.g., a `Queue` or a global variable) that the UI loop reads from.
**However**, mixing sync callbacks with async UI is complex.

**Better Alternative for Stability**:
I will stick to `app.astream_events` BUT I will filter the events more strictly and handle the Pydantic warning/error if possible.
Actually, the logs showed `UserWarning: Received a Pydantic BaseModel V1 schema`. This is just a warning.
The real issue might be that `astream_events` yields a huge number of events, and maybe my processing logic in `main.py` is too slow or error-prone.

**Decision**:
I will modify `src/main.py` to:
1.  Use `app.stream()` for the main logic flow (because it's proven to work).
2.  **Sacrifice the granular token streaming** for now to restore functionality. The user said "流程没有正常跑下去" (Process didn't run normally), so functionality is P0.
3.  **Simulation**: I will simulate the "Thinking..." effect by showing a spinner during the `app.stream` execution of each node.

**Wait**, the user specifically asked for "流式输出思考过程" (Stream thinking process). I cannot just remove it.
I must make `astream_events` work or use a callback.

**Let's try to fix `astream_events` usage**:
The error I suppressed was likely crucial. I will:
1.  Add logging to a file in `src/main.py` to see exactly *what* error was thrown.
2.  BUT I don't want to waste a turn logging.
3.  I suspect the `chunk.content` access in `on_chat_model_stream` might be failing for some chunks (e.g. function calls).
4.  Also, `Supervisor` uses structured output (Pydantic v1), which might break `astream_events` serialization if not handled.

**Refined Plan**:
1.  Modify `src/main.py` to use `app.astream_events` but with **safeguards**.
    *   Check if `chunk` has `content` attribute safely.
    *   Check if `data` has `output` safely.
    *   **Crucially**: The `Supervisor` node returns a Pydantic object (`RouteResponse`) wrapped in a dict `{'next': ...}`. The `astream_events` serializer might struggle with Pydantic v1 objects if they are in the output.
    *   I will modify `src/agents/supervisor.py` to return a **pure dict** instead of a Pydantic object in the state, although it already returns `{"next": result.next}` which is a string. So that should be fine.
    *   Wait, the `Supervisor` *internal* chain returns a Pydantic object. `astream_events` sees internal chain outputs too.

**Action**:
I will update `src/main.py` to be extremely defensive in the `async for` loop, ensuring it continues even if one event is malformed. And I will add a fallback: if `astream_events` yields nothing for 5 seconds, it should warn.

**Actually**, looking at `debug_graph.py` output:
`Output: {'next': 'ClarifyIntent'}`
The nodes return simple dicts.
The issue is likely the `mem0` error or similar network glitches causing `astream_events` to time out or break connection if not handled async-correctly.

I will rewrite `src/main.py` to:
1.  Use `app.stream()` (the reliable one) for the logic.
2.  Use a `AsyncIteratorCallbackHandler` passed to `config` to capture tokens for the UI. This separates the logic (reliable) from the visualization (streaming tokens).
    *   Actually, `app.stream` doesn't support async callbacks easily in a sync graph (the graph is compiled synchronously? No, `create_graph` uses `StateGraph`, and we call `app.stream` or `app.astream`).
    *   If I use `app.astream`, I can pass async callbacks.

**Let's try a hybrid approach in `src/main.py`**:
Keep `astream_events` but:
1.  Filter events to *only* `on_chat_model_stream` and `on_chain_end` of the specific nodes I care about.
2.  Catch errors *per event processing* so one bad event doesn't kill the loop.
3.  **Most importantly**: The previous code had `live.update` *inside* the high-frequency loop. This might be too heavy. I will throttle the UI updates.

**Let's go.**

Tasks:
1.  Modify `src/main.py`:
    *   Throttle UI updates (every 0.1s or so).
    *   Add defensive checks for `chunk.content`.
    *   Add defensive checks for `on_chain_end` data structure.
    *   Restore the error printing (to console or file) to see if it's failing.

Wait, I saw `search` tool result for `src/agents/execute.py` showing lines 1-47. The file is small.
The user reported "流程没有正常跑下去" after I added `pass`.
This means it just sat there.

I will reimplement `main.py` to use `app.astream` (not events) for the flow control, and maybe give up on token streaming *temporarily* to prove I can fix the "not running" issue, OR (better) use `astream_events` but debug the specific error.

I will try one more time to fix `astream_events` in `main.py` by making it robust. I suspect `mem0` 404 error might be raising an exception that `astream_events` bubbles up, crashing the stream generator itself.

I'll also patch `src/agents/clarify.py` to catch that `mem0` error more aggressively so it doesn't bubble up. The debug log showed it caught it, but maybe not fully.

**Actually, I will switch to `app.astream` (standard streaming) which yields state updates.**
This is what `debug_graph.py` did and it worked.
To get "Thinking" tokens, I will rely on the fact that `app.astream` *doesn't* give tokens.
So I will have to sacrifice the "Thinking" token stream to ensure stability, **OR** use `stream_mode="updates"` which is standard.

**Compromise**: I will use `app.astream()` to drive the Plan Table (this fixes the "process not running" issue).
For the "Thinking" panel, I will just show "Agent is thinking..." without the tokens.
**Why?** Because `astream_events` seems to be the source of instability (serialization, Pydantic versions, etc.). The user's primary need is "Run the project" (functionality).
I will explain this trade-off if needed, or I can try to use a callback.

**Let's try `app.astream` + `Callbacks`**.
I can define a `RichTokenHandler(BaseCallbackHandler)` that updates a global variable `current_thinking`.
The main loop runs `app.invoke(..., config={"callbacks": [handler]})`.
The main loop also runs a background task that updates the `Live` display from `current_thinking`.
This is a standard pattern for TUI + Streaming.

**Plan**:
1.  Create `src/utils/ui.py` with `RichTokenHandler`.
2.  Update `src/main.py`:
    *   Use `app.invoke` (or `app.astream` for steps) with this callback.
    *   Run UI update loop in parallel.

This is too complex for a quick fix.

**Simplest Fix**:
Just use `app.stream` (like `debug_graph.py`) in `src/main.py`.
It will update the Plan Table step-by-step.
For the "Thinking" part, just show a static "Thinking..." or "Processing...".
This guarantees the "flow runs normally".
If the user really wants streaming tokens, I can add it later when stability is ensured.
**BUT** the user explicitly asked for "thinking process stream".
So I will try `astream_events` **one last time** with:
1.  **Filtering**: Only listen to `on_chat_model_stream` from `ChatOpenAI` (check tags/names).
2.  **Error Handling**: Wrap the *iterator* in try-except (if the generator crashes).

```python
try:
    async for event in app.astream_events(...):
        # ... logic
except Exception as e:
    console.print(f"Stream error: {e}")
    # Fallback: maybe run invoke() if stream fails?
```
The previous code *did* wrap the loop in try-except. And I suppressed it. So it finished silently.
The fact that it finished means the generator raised an error.
The error in `debug_graph` logs was:
`UserWarning: Received a Pydantic BaseModel V1 schema...`
`mem0` 404 error.
These shouldn't crash `app.stream`.

**Wait**, `debug_graph.py` used `app.stream`. `main.py` used `app.astream_events`.
`astream_events` is much more sensitive.
I will switch `main.py` to use `app.stream` (to ensure completion) AND use `callbacks` for token streaming.
This is the robust architectural choice.

**Steps**:
1.  Define a simple `AsyncIteratorCallbackHandler` or similar in `main.py` (or utils).
2.  Pass it to `app.astream`.
3.  Actually, `app.astream` yields state updates. The callback will handle token printing.

Let's do this. It's cleaner.