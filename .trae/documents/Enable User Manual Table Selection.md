# Enable User Manual Table Selection

This plan adds support for users to manually select or adjust the relevant tables for their query, overriding or augmenting the agent's automatic selection.

## 1. Backend Updates

### `src/state/state.py`
-   Update `AgentState` to include `manual_selected_tables` (list of table names).

### `src/agents/select_tables.py`
-   Modify `select_tables_node` to respect manual selection.
-   **Logic**:
    -   If `manual_selected_tables` is present in state:
        -   Fetch schema for these tables directly.
        -   Optionally, still run auto-selection and merge, OR strictly use manual selection.
        -   **Decision**: Merge manual selection with auto-selection if the user intent implies "also look at...", but typically manual selection implies "limit to these".
        -   **Revised Logic**: If manual selection exists, use it as the *primary* source. If the user query is new, we might still want to search, but for now, let's treat manual selection as an override or a filter.
        -   Actually, the best UX is: Agent proposes tables -> User sees them -> User edits them -> Agent proceeds with edited list.
        -   **Proposed Flow**:
            1.  Frontend sends `manual_tables` in the request if the user has selected them in the UI.
            2.  If `manual_tables` are provided, skip the search step and use them directly.
            3.  If no `manual_tables`, run the search agent.

### `src/server.py`
-   Update `ChatRequest` model to accept `selected_tables: Optional[List[str]]`.
-   Pass this to the graph input.

## 2. Frontend Updates

### `frontend/src/App.tsx`
-   **Checkbox Selection**: The `DirectoryTree` already supports `multiple` and checkboxes (`checkable`).
-   **State Management**: Track `checkedKeys` in `App` state.
-   **Interaction**:
    -   When user checks tables in the sidebar, store them.
    -   When sending a message, include `selected_tables` in the payload.
-   **Visual Feedback**:
    -   When the agent selects tables (in `SelectTables` node), highlight/check them in the tree automatically so the user sees what was selected.
    -   Allow user to uncheck/check to refine for the *next* turn or restart.

## 3. Execution Plan
1.  **Frontend**: Enable checkboxes in `DirectoryTree`. Track selection. Update `handleSendMessage` to send selection.
2.  **Backend - Server**: Update `ChatRequest` to accept `selected_tables`.
3.  **Backend - Agent**: Update `select_tables_node` to prioritize `selected_tables` if provided.
4.  **Feedback Loop**: Ensure the agent's *auto-selected* tables are sent back to frontend to update the selection state (so the user sees what the agent picked).

## Refined Flow for "User Adjustment"
The user wants to *adjust* the scope.
-   **Scenario A (Pre-selection)**: User checks "hr_employees" then types "count employees". Agent uses "hr_employees".
-   **Scenario B (Post-selection/Correction)**: Agent picks "hr_employees". User sees it, thinks "wait, I need departments too", checks "hr_departments", and says "redo" or "also departments".
-   **Technical implementation**:
    -   Frontend: `checkedKeys` state.
    -   Backend: If `selected_tables` is not empty, fetch their schemas. If empty, perform search.
    -   **Important**: If the user *manually* selects tables, we should probably *skip* the semantic search to give them full control, OR use the manual selection as a hard filter. Let's go with: **If manual selection > 0, use ONLY those tables.** This gives precise control.

## Auto-Selection Feedback
-   When `SelectTables` node runs, it produces `relevant_schema`. We should parse the table names from this and send a specific event `event: tables_selected` to the frontend so it can update the checkboxes.

