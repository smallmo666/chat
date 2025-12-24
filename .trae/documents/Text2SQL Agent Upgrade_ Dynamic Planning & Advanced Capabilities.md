# Text2SQL Agent Upgrade: Dynamic Planning & Advanced Capabilities

This plan implements a major upgrade to the Text2SQL agent, transforming it from a fixed-flow pipeline into a dynamic, intent-driven autonomous agent with advanced data analysis and visualization capabilities.

## 1. Architecture: Dynamic Planning (智能体制定独立可行的计划)

We will replace the rigid rule-based Supervisor with a **Planner-Dispatcher** model.

### New `Planner` Node
-   **Role**: Analyzes user intent at the start of a turn and generates a sequence of execution steps (The Plan).
-   **Intelligent Intent Recognition**:
    -   **Data Query**: Plan -> `SelectTables` -> `GenerateDSL` -> `DSLtoSQL` -> `ExecuteSQL` -> `DataAnalysis` -> `Visualization`.
    -   **Schema Inquiry** ("What tables do you have?"): Plan -> `TableQA`.
    -   **Deep Analysis** ("Why is sales dropping?"): Plan -> `SelectTables` -> ... -> `DeepInsight`.
-   **Output**: A list of steps stored in `AgentState`, e.g., `[{"id": "SelectTables", "desc": "选择相关表"}, {"id": "ExecuteSQL", "desc": "执行查询"}, ...]`.

### Updated `Supervisor` (Dispatcher)
-   **Role**: Executes the plan sequentially.
-   **Logic**: Checks `current_step_index` in `AgentState` and routes to the corresponding node in the plan.

## 2. New Capability Nodes (新增能力节点)

### `DataAnalysis` (数据解读 & 洞察)
-   **Function**: Takes SQL query results and user question.
-   **Output**: Generates a natural language summary, highlighting key trends, anomalies, or answers.
-   **Tech**: LLM-based analysis.

### `Visualization` (可视化图表)
-   **Function**: Analyzes data structure (categorical/numerical columns) and user intent.
-   **Output**: Generates an **ECharts** configuration JSON (e.g., Bar, Line, Pie, Scatter).
-   **Frontend**: Renders the chart using `echarts-for-react`.

### `TableQA` (表信息助手)
-   **Function**: Uses RAG (Retrieval-Augmented Generation) over the database schema to answer questions about table definitions, column meanings, etc.

## 3. Frontend Upgrades (React + TS + ECharts)

### Dynamic Steps Component
-   Replace hardcoded steps with a dynamic list driven by the backend `plan` event.
-   Visualizes the agent's thought process in real-time.

### Rich Content Rendering
-   **Charts**: Integrate `echarts` and `echarts-for-react` to render interactive charts from the agent's output.
-   **Markdown**: Use `react-markdown` to render the Data Analysis text with proper formatting (tables, bolding, lists).

### Mixed Mode Interaction
-   **Manual Control**: Continue supporting manual table selection.
-   **Feedback Loop**: Allow users to refine the plan (e.g., "Change to Line Chart", "Analyze by Region instead").

## 4. Execution Roadmap

1.  **Frontend Dependencies**: Install `echarts`, `echarts-for-react`, `react-markdown`.
2.  **Backend State**: Update `AgentState` to support `plan`, `visualization`, `analysis`.
3.  **Implement Agents**:
    -   Create `planner.py`, `analysis.py`, `visualization.py`, `table_qa.py`.
    -   Refactor `supervisor.py` to dispatch based on plan.
4.  **Graph Orchestration**: Update `src/graph.py` to wire up the new nodes.
5.  **Frontend Implementation**: Update `App.tsx` to render dynamic steps, charts, and markdown analysis.

