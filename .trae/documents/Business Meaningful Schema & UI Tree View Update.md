# Business Meaningful Schema & UI Tree View Update

This plan addresses the requirement to make the generated schema more business-meaningful (standardized names, Chinese comments, correct types) and to display a tree view (Table -> Columns) in the frontend sidebar.

## 1. Data Generation Update (`src/utils/db.py`)
The current `create_dummy_table` generates generic columns (`code`, `description`). We need to specialize this based on the "category" of the table to provide realistic business context.

### Strategy: Category-Based Schema Templates
We will define templates for different business domains.
-   **Analytics (`logs_*`)**: `log_id` (BIGINT), `user_id` (INT), `action_type` (VARCHAR), `ip_address` (VARCHAR), `device_info` (JSON), `created_at` (DATETIME). **Chinese**: `日志ID`, `用户ID`, `操作类型`, `IP地址`, `设备信息`, `创建时间`.
-   **Inventory (`inventory_*`)**: `sku_id` (VARCHAR), `warehouse_id` (INT), `quantity` (INT), `reserved_qty` (INT), `last_restock_date` (DATE). **Chinese**: `SKU编号`, `仓库ID`, `库存数量`, `预留数量`, `最后补货日期`.
-   **Report (`report_*`)**: `report_date` (DATE), `metric_name` (VARCHAR), `metric_value` (DECIMAL), `dimension` (VARCHAR). **Chinese**: `报表日期`, `指标名称`, `指标值`, `维度`.
-   **System (`sys_config_*`)**: `config_key` (VARCHAR), `config_value` (TEXT), `is_enabled` (BOOLEAN), `updated_by` (VARCHAR). **Chinese**: `配置键`, `配置值`, `是否启用`, `更新人`.

**Implementation Details**:
-   Update `create_dummy_table` to accept a schema definition dictionary.
-   Use `COMMENT` in SQL `CREATE TABLE` statements to store Chinese names for tables and columns.
-   Update `ensure_demo_data` to apply these templates.

## 2. API Update (`src/server.py`)
The current `GET /tables` endpoint only returns a list of strings (table names). We need to return a hierarchical structure.

### New Response Format
```json
{
  "tables": [
    {
      "name": "users",
      "comment": "用户信息表",
      "columns": [
        {"name": "id", "type": "INTEGER", "comment": "用户ID"},
        {"name": "name", "type": "VARCHAR(255)", "comment": "姓名"}
      ]
    },
    ...
  ]
}
```

### Implementation
-   Update `get_tables` in `src/server.py`.
-   Since inspecting 1000 tables for columns in real-time is slow, we should read from the `AppDatabase`'s stored schema (which is already JSON) instead of live inspection of `QueryDatabase`.
-   We already have `app_db.get_stored_schema_info()` which returns the full JSON. We can just serve that!

## 3. Frontend Update (`frontend/src/App.tsx`)
Replace the flat `Menu` with a `Tree` component to show tables and their columns.

### UI Changes
-   **Component**: Use Ant Design `Tree` or `DirectoryTree`.
-   **Data Structure**: Convert the API response into TreeData format.
    -   Level 1: Table Nodes (Icon: Table). Label: `TableName (中文名)`
    -   Level 2: Column Nodes (Icon: Column). Label: `ColName (Type) - 中文名`
-   **Search**: Update search to filter both table names and column names/comments.

## Execution Plan
1.  **Backend - DB Utils**: Refactor `ensure_demo_data` to use business-meaningful schemas with comments.
2.  **Backend - Server**: Update `GET /tables` to return full schema info (using cached data from AppDB to ensure performance).
3.  **Frontend**: Replace Sidebar List with a Tree View component displaying detailed column info.
