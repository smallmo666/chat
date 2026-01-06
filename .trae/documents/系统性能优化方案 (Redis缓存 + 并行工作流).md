# 系统性能提升与接口耗时降低方案 (V5.2)

基于对当前架构的深度分析，该项目已经采用了 `Async/Await`、`Semantic Cache (ChromaDB)` 和 `SQLAlchemy Async Engine` 等先进技术。但在高并发场景和复杂工作流中，仍有进一步优化的空间。

我为您设计了以下 **"三层加速"** 方案，旨在从**数据库层**、**应用层**到**模型层**全方位降低延迟。

## 1. 数据库 Schema 缓存 (Redis) - *高收益*
*   **痛点**: `SelectTables` 和 `GenerateDSL` 节点每次运行时，都需要调用 `inspect_schema`。这是一个**同步**且耗时的操作（即使被包装在 `to_thread` 中），在大表数据库中可能耗时 1-3 秒。
*   **方案**: 引入 Redis 缓存 Schema 信息。
    *   **实现**: 在 `QueryDatabase.inspect_schema` 中增加 Redis 缓存层。
    *   **策略**: Key 为 `schema:{project_id}:{scope_hash}`，过期时间设为 1 小时（或手动刷新）。
    *   **预期**: 再次查询时 Schema 获取时间从秒级降至毫秒级。

## 2. LLM 并行执行 (Parallel Execution) - *架构优化*
*   **痛点**: 目前工作流中 `DataDetective` (数据侦探) 和 `KnowledgeRetrieval` (知识检索) 是串行执行的。它们之间没有依赖关系。
*   **方案**: 修改 LangGraph 拓扑，使这两个节点**并行运行**。
    *   **实现**: 在 `CacheCheck` 之后，同时分叉出 `DataDetective` 和 `KnowledgeRetrieval` 分支，最后汇聚到 `Planner`。
    *   **预期**: 总体耗时减少 `min(Detective_Time, Knowledge_Time)`。

## 3. SQL 查询结果缓存 (Query Caching) - *体验优化*
*   **痛点**: 用户经常会重复点击相同的仪表盘或查询相同的数据，重复执行 SQL 既慢又浪费数据库资源。
*   **方案**: 基于 SQL 语句的哈希值缓存查询结果。
    *   **实现**: 在 `QueryDatabase.run_query_async` 中，在执行 SQL 前先计算 Hash，检查 Redis 是否存在结果。
    *   **策略**: Key 为 `sql_result:{project_id}:{sql_hash}`，TTL 5 分钟（适合实时性要求不极端的场景）。

---

## 实施路线图

建议优先实施 **Schema 缓存** 和 **并行执行**，这两项改动风险小且收益立竿见影。

1.  **环境准备**: 确保 Redis 连接配置正确 (`src/core/redis_client.py` - 需创建)。
2.  **Schema 缓存**: 修改 `src/core/database.py`。
3.  **并行工作流**: 修改 `src/workflow/graph.py`。
4.  **SQL 结果缓存**: 修改 `src/core/database.py`。
