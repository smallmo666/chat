# Scale to 1000 Tables & Multi-Table Query & UI Update

This plan outlines how to scale the current demo to support 1000 tables, enable multi-table query capabilities, and add a database schema browser to the UI.

## 1. Data Generation (Backend)
We need to generate 1000 tables with realistic relationships to test multi-table joins.

### `src/utils/db.py`
-   **Modify `ensure_demo_data`**:
    -   Instead of just `users`, creating 1000 tables (e.g., `table_001` to `table_1000`).
    -   **Strategy**: Create clusters of related tables (e.g., e-commerce domain: `orders`, `products`, `customers`, `inventory`, etc., or just randomized schemas with foreign keys).
    -   **Simplified Approach**: Create `users`, `orders`, `products`, `categories` as core tables, and then generate `extra_table_N` to reach 1000.
    -   **Optimization**: Ensure we don't recreate them if they exist to save startup time.

### `src/utils/db.py` (Schema Inspection Optimization)
-   **Modify `inspect_schema`**:
    -   **Problem**: Inspecting 1000 tables and dumping all columns into a single string will exceed LLM context windows (1000 tables * ~5 cols * ~20 chars ≈ 100k+ chars).
    -   **Solution**: Implement **RAG (Retrieval-Augmented Generation)** for Schema.
        -   Instead of returning *all* schema info, we need a way to *search* for relevant tables based on the user query.
        -   We can use a vector store (Chroma/FAISS) or simple keyword search if table names are semantic.
        -   **Action**: Update `AppDatabase` to store schema in a structured way (JSON) rather than a single text block, or index it.

## 2. Agent Workflow Update (Backend)
To support 1000 tables, we cannot pass the full schema to the `GenerateDSL` and `DSLtoSQL` agents. We need a new node to "Select Relevant Tables".

### New Graph Node: `SelectTables`
-   **Purpose**: Given the user query, identify which of the 1000 tables are relevant.
-   **Input**: User Query.
-   **Output**: List of relevant table names + their schemas.
-   **Implementation**:
    -   Create `src/agents/select_tables.py`.
    -   Use an LLM (or embedding search) to map "User Query" -> "Top 5-10 Relevant Tables".
    -   Update `state/state.py` to include `relevant_schema_info`.

### Graph Update (`src/graph.py`)
-   Insert `SelectTables` node *after* `ClarifyIntent` and *before* `GenerateDSL`.
-   Flow: `Supervisor` -> `ClarifyIntent` -> `Supervisor` -> `SelectTables` -> `GenerateDSL` -> `DSLtoSQL` -> `ExecuteSQL`.
-   Actually, `Supervisor` might just route to `SelectTables` first if intent is clear.

### Agent Updates
-   **`GenerateDSL`**: Use `relevant_schema_info` from state instead of fetching full schema.
-   **`DSLtoSQL`**: Use `relevant_schema_info` from state.

## 3. API Update (`src/server.py`)
-   **New Endpoint**: `GET /tables`
    -   Returns a list of all table names (and maybe brief descriptions) for the UI sidebar.
    -   Pagination might be needed if 1000 tables are too heavy for one request, but for 1000 names (strings), ~20KB is fine.

## 4. Frontend Update (`frontend/`)
-   **New Component**: `SchemaBrowser` (Left Sidebar).
    -   Displays a list of database tables.
    -   Search/Filter input to find tables.
    -   Click to expand and show columns (optional).
-   **Layout**:
    -   Update `App.tsx` to add a new Splitter panel or Drawer for the Database Schema.
    -   Maybe a tab in the left panel alongside "Chat"? Or a 3-column layout: [Schema] [Chat] [Plan].

## Execution Plan
1.  **Backend - DB Utils**: Update `ensure_demo_data` to generate 1000 tables. Update `inspect_schema` to support RAG/Filtering.
2.  **Backend - RAG/Search**: Implement a simple semantic search or keyword search for table selection in `src/utils/schema_search.py`.
3.  **Backend - New Agent**: Create `SelectTables` node and update `Graph`.
4.  **Backend - API**: Add `GET /schema` endpoint.
5.  **Frontend**: Implement Schema Browser sidebar.
