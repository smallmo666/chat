# Implementation Plan: Hybrid Search & Context Optimization

I will enhance the schema retrieval accuracy with vector search and improve the SelectTables agent's ability to handle multi-turn conversations.

## 1. Hybrid Search Implementation
**Goal**: Integrate ChromaDB for semantic vector search to complement the existing keyword-based heuristic.

**File**: [`src/utils/schema_search.py`](src/utils/schema_search.py)
- **Vector DB Integration**:
    - Update `SchemaSearcher` to initialize a ChromaDB client.
    - Implement `_init_vector_db()` method to populate the vector store with table descriptions (TableName + Comment) if it's empty.
- **Hybrid Logic**:
    - Modify `search_relevant_tables`:
        - **Vector Path**: Query ChromaDB for top-k semantically similar tables.
        - **Keyword Path**: Keep the existing heuristic scoring as a fast fallback/booster.
        - **Fusion**: Merge results from both paths (weighted union) to form the candidate list for the LLM.

## 2. Multi-turn Context Optimization
**Goal**: Enable `SelectTables` agent to resolve pronouns and implicit references (e.g., "how about the orders?" referring to previously discussed users).

**File**: [`src/agents/select_tables.py`](src/agents/select_tables.py)
- **Context Awareness**:
    - Instead of just grabbing `last_human_msg`, retrieve the last `N` messages from `state["messages"]`.
- **Query Rewriting (Self-Correction)**:
    - Introduce a lightweight LLM call *before* search to rewrite the user query into a standalone search query.
    - **Prompt**: "Given the chat history and the latest user input, rewrite the input to be a self-contained search query for database tables. Resolve any pronouns."
    - Use this rewritten query for the `SchemaSearcher`.

## 3. Dependency Management
**File**: [`pyproject.toml`](pyproject.toml)
- Ensure `chromadb-client` and `langchain-chroma` (or `langchain-community` with vector store support) are available. (Already present in `uv.lock` but verifying usage).

## Verification Plan
- **Hybrid Search**: Verify that searching for "revenue" retrieves `orders` table even if the word "revenue" isn't in the table name (semantic match).
- **Context**:
    - Turn 1: "Show me all users."
    - Turn 2: "Which ones bought iPhone?"
    - Verify Turn 2 correctly retrieves `orders` and `products` tables by resolving "ones" to users and understanding the purchase context.
