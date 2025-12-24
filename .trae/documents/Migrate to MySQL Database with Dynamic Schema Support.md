I will migrate the project from the mock SQLite database to the specified MySQL database.

### 1. Dependency Management
I will add the necessary Python libraries for MySQL connection:
- `pymysql`: MySQL driver.
- `sqlalchemy`: Database toolkit for robust connection and Pandas integration.
- `cryptography`: Often required for MySQL authentication.

### 2. Configuration (`.env`)
I will update the `.env` file with the provided credentials:
- **Host**: `159.75.148.55`
- **Port**: `3306`
- **User**: `root` (Defaulting to root since no username was provided)
- **Password**: `123456`
- **Database**: `testdb`

### 3. Database Utility Refactoring (`src/utils/db.py`)
I will rewrite `MockDB` to be a real `MySQLDB` class using `SQLAlchemy`:
- **Connection**: Establish a real connection pool.
- **Schema Introspection**: Implement a `get_schema()` method to dynamically fetch table and column names from the `testdb` database.
- **Demo Compatibility**: I will add a check to see if the `users` table exists. If not, I will create and seed it so the current demo task ("Find users in 2023") continues to work.

### 4. Agent Prompt Updates (Dynamic Schema)
To make the agent truly intelligent, I will update the agents to use the *real* database schema instead of hardcoded strings:
- **`src/agents/gen_dsl.py`**: Update the prompt to inject the result of `get_schema()`.
- **`src/agents/dsl2sql.py`**: Update the prompt to include the actual table definitions.

### 5. Verification
I will run `src/main.py`. It will:
1. Connect to the MySQL database.
2. Print the detected schema.
3. Ensure the `users` table exists (or create it).
4. Run the demo query against the real remote database.