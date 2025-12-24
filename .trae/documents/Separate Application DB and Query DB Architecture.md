I will re-architect the database layer to support the separation of concerns: **Application DB** (`testdb`) for metadata/schema storage, and **Query DB** (`querydb`) for data execution and testing.

### 1. Configuration (`.env`)
I will update the `.env` file to include credentials for both databases:
-   `APP_DB_*`: Connects to `testdb` (User: `testdb`, Pass: `123456`).
-   `QUERY_DB_*`: Connects to `querydb` (User: `querydb`, Pass: `7e6Dzi8kHcMDMDiX`).

### 2. Database Utility Refactoring (`src/utils/db.py`)
I will split the single `Database` class into two specialized classes:
-   **`QueryDatabase`**:
    -   Connects to `querydb`.
    -   `ensure_demo_data()`: Creates and seeds the `users` table in `querydb` (Generates test data).
    -   `run_query()`: Executes the generated SQL against `querydb`.
    -   `inspect_schema()`: Reads the raw schema from `querydb`.
-   **`AppDatabase`**:
    -   Connects to `testdb`.
    -   `init_metadata_table()`: Creates a `db_schema_info` table to store schema metadata.
    -   `save_schema_info(schema)`: Persists the schema information from `querydb` into `testdb`.
    -   `get_stored_schema_info()`: Retrieves the schema info for the Agents to use.

### 3. Logic Update (`src/main.py`)
I will update the initialization flow:
1.  Initialize `QueryDatabase` and `AppDatabase`.
2.  Run `query_db.ensure_demo_data()` to ensure `querydb` has the test data.
3.  Run `query_db.inspect_schema()` to get the latest schema.
4.  Run `app_db.save_schema_info(...)` to sync this info to `testdb`.

### 4. Agent Updates
-   **`GenerateDSL` & `DSLtoSQL` Agents**: Will now call `app_db.get_stored_schema_info()` to get context (fulfilling "store querydb table info in testdb").
-   **`ExecuteSQL` Agent**: Will call `query_db.run_query()` to execute the SQL (fulfilling "execute SQL on querydb").

This design strictly follows your requirement: `testdb` manages metadata/persistence, while `querydb` handles the actual data query execution.