# Build FastAPI Backend with Streaming & React Frontend

This plan involves creating a FastAPI server to expose the Text2SQL agent and a React + TypeScript + Ant Design frontend to interact with it.

## 1. Backend: FastAPI Server (`src/server.py`)
We will create a new server entry point that provides a streaming API for the agent.

### Features
- **Endpoint**: `POST /chat`
- **Streaming Protocol**: Server-Sent Events (SSE) using `StreamingResponse`.
- **Event Types**:
    - `step`: Updates on the execution plan (e.g., "ClarifyIntent started", "completed").
    - `thinking`: Real-time token stream from the LLM.
    - `result`: The final answer or clarification question.
    - `error`: Error messages.
- **Concurrency**: Use `asyncio.Queue` to bridge the LangGraph execution loop and the LLM token callbacks into a single response stream.

### Implementation Details
- **Dependencies**: Add `fastapi`, `uvicorn`.
- **Logic**:
    - Create a background task to run `app.astream`.
    - Use a custom `AsyncCallbackHandler` to push tokens to a queue.
    - Push graph state updates to the same queue.
    - The API response yields data from the queue until execution finishes.

## 2. Frontend: React + TS + Antd (`frontend/`)
We will scaffold a modern frontend to visualize the chat and the agent's thinking process.

### Features
- **Chat Interface**: Standard message list (User vs. Agent).
- **Thinking Process**: A collapsible or dedicated area showing the real-time "Thought Chain" and Plan execution status.
- **UI Framework**: Ant Design for polished components (Steps, Card, Input, Button).
- **Tech Stack**: Vite, React, TypeScript.

### Implementation Steps
1.  Initialize Vite project in `frontend/`.
2.  Install `antd`, `axios` (or fetch), `lucide-react`.
3.  **Components**:
    - `ChatBox`: Displays messages.
    - `PlanViewer`: Visualizes the 4 steps (Clarify -> DSL -> SQL -> Execute) with status icons.
    - `ThinkingConsole`: Shows the streaming tokens.
4.  **Integration**:
    - Connect to `http://localhost:8000/chat`.
    - Parse SSE stream to update state incrementally.

## 3. Execution Steps
1.  **Backend Setup**:
    - Add dependencies (`fastapi`, `uvicorn`).
    - Create `src/server.py`.
2.  **Frontend Setup**:
    - Create `frontend` directory.
    - Run `npm create vite`.
    - Install dependencies.
    - Implement UI code.
3.  **Run & Verify**:
    - Launch Backend.
    - Launch Frontend.
    - Test the full loop.
