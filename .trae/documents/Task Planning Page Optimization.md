# Task Planning Page Optimization (任务规划页面优化)

This plan focuses on enhancing the "Execution Plan Tracking" (执行计划追踪) sidebar to be more informative, visual, and time-aware, as requested.

## 1. Goal
Optimize the task planning UI to show a checklist of tasks for the current turn, displaying the thinking process, execution results, progress status, and elapsed time for each step.

## 2. Frontend Changes (`App.tsx`)

### 2.1 New Data Structures
Define a richer `TaskItem` interface to replace the simple `PlanStep`.
```typescript
interface TaskItem {
    id: string;          // Unique ID (e.g., node name)
    title: string;       // Task description (e.g., "Generate SQL")
    status: 'pending' | 'process' | 'success' | 'error';
    startTime?: number;  // Timestamp when task started
    endTime?: number;    // Timestamp when task finished
    duration?: number;   // Duration in ms
    logs: string[];      // Thinking process logs for this step
    result?: string;     // Summary of the result
}
```

### 2.2 UI Redesign (Right Sidebar)
Replace the simple Ant Design `Steps` component with a custom `Timeline` or enhanced `List` view that includes:
-   **Task Title**: Bold text.
-   **Status Icon**: Spinner for processing, Check for success.
-   **Time Info**: "0.5s", "1.2s" badge.
-   **Collapsible Details**:
    -   **Thinking Process**: Small text logs (streaming).
    -   **Result**: Short summary (e.g., "Generated SQL: SELECT ...").

### 2.3 Logic Updates
-   **Start Task**: When receiving a `step_start` event (need to add this event type from backend or infer it), record `startTime`.
-   **Update Task**: When receiving `thinking` events, append to the *current* active task's logs.
-   **Finish Task**: When receiving `step` (completion) event, record `endTime`, calculate duration, and set status to `success`.

## 3. Backend Changes (`src/server.py` & `src/agents/*.py`)

### 3.1 Event Granularity
Currently, the backend sends:
-   `plan`: The initial list of steps.
-   `thinking`: Streaming tokens (global).
-   `step`: Completion of a step.

**New Flow**:
-   **`step_start`**: Supervisor sends this before routing to a node.
-   **`thinking`**: Associate thinking logs with the *current* active node.
-   **`step_end`**: (Existing `step` event) Send completion signal.

### 3.2 Supervisor Update
Update `supervisor_node` or the graph execution loop in `server.py` to explicitly emit a `step_start` event when a node begins execution.
*Actually, since `server.py` iterates over `graph_app.astream`, it sees the output *after* the node finishes. To get start times, we might need to rely on the *end* of the previous step triggering the start of the next, or use a callback in LangGraph.*
*Simplification*: The `server.py` knows the `plan`. When `plan` is generated, all tasks are `pending`.
-   When `plan` event is sent, frontend initializes the list.
-   The first task starts immediately.
-   When `step` (completion) event arrives for Task N, Task N finishes, and Task N+1 starts automatically.
-   **Duration Calculation**: Frontend can calculate duration locally (`now - taskStartTime`). Backend doesn't strictly need to send it, but sending server-side duration is more accurate.

**Refined Backend Strategy**:
-   Modify `server.py`'s `event_generator` to calculate and send `duration` in the `step` event.
-   We don't need a separate `step_start` event if we assume sequential execution: Step N+1 starts when Step N ends.

## 4. Implementation Steps
1.  **Frontend**: Update `PlanStep` interface to include `startTime`, `endTime`, `duration`, `logs`.
2.  **Frontend**: Create a new `TaskTimeline` component to render the rich task list.
3.  **Frontend**: Update `handleSendMessage` to:
    -   Initialize tasks from `plan` event.
    -   Update `currentTask` with `thinking` content.
    -   Mark task as done and calculate duration on `step` event.
4.  **Backend**: (Optional but good) Add `start_time` tracking in `server.py` loop to compute precise server-side duration for each step.

