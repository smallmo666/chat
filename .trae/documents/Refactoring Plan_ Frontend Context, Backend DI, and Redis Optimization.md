# Refactoring Plan

## 1. Frontend Refactoring & State Management
**Goal**: Complete the frontend modernization by introducing Context API to manage global state, replacing prop drilling.
- **Create `SchemaContext`**:
    - Create `frontend/src/context/SchemaContext.tsx`.
    - Define `SchemaProvider` to manage `dbTables`, `checkedKeys`, and the `fetchTables` logic.
- **Refactor `App.tsx`**:
    - Wrap the application with `SchemaProvider`.
    - Remove `dbTables` and `checkedKeys` state and `fetch` logic from `App.tsx`.
    - Use `useContext` to access these values where needed (or let child components access them).
- **Refactor `SchemaBrowser.tsx`**:
    - Update to consume `SchemaContext` instead of receiving props.

## 2. Backend Architecture: Dependency Injection
**Goal**: Decouple database access to support better testing and concurrency.
- **Refactor `src/utils/db.py`**:
    - Create a `DatabaseProvider` class to manage instances.
    - Rewrite `get_query_db` and `get_app_db` to use this provider.
    - Ensure these functions can be used as FastAPI dependencies (`Depends`).
- **Update `src/server.py`**:
    - Inject database dependencies into endpoints (`/tables`, `/admin/regenerate`) using `Depends(get_query_db)`.
    - *Note*: For the Graph execution, we will ensure the `db` accessor is robust, though full graph node refactoring is out of scope for this step to maintain stability.

## 3. Performance Optimization: Redis Storage
**Goal**: Optimize Agent state storage to reduce payload size and improve speed.
- **Refactor `src/utils/simple_redis_saver.py`**:
    - **Incremental Storage**: Switch from storing the entire checkpoint as a single pickled blob to using Redis Hashes (`HSET`).
    - **Strategy**: Store `checkpoint` fields (like `channel_values`) as individual hash fields. This allows updating/reading only parts of the state if needed in the future, and prevents overwriting the entire key if we were to support partial updates.
    - **Compression**: Apply `zlib` compression to the serialized data to further reduce Redis memory usage and network I/O.
