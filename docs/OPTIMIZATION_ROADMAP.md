# 项目架构与功能优化路线图 (Optimization Roadmap)

本文档详细记录了 Text2SQL 智能体项目的架构演进方向和功能优化计划。

## 1. 现状总结 (Current Status)

经过早期的重构与优化，项目已具备以下特性：
*   **架构**: 基于 LangGraph 的多智能体协作架构 (Planner -> Supervisor -> Workers)。
*   **安全**: 实现 `StatefulSandbox` (Python 沙箱) 和 `is_safe_sql` (AST 检查)，保障代码执行安全。
*   **交互**: 支持 Matplotlib 绘图并自动回传图像数据。
*   **规范**: 核心模块全面汉化，统一使用 Pydantic 进行类型定义。

## 2. 架构演进规划 (Architecture Evolution)

### Phase 1: 高并发异步基座 (已排期)
**目标**: 消除同步 I/O 阻塞，提升系统吞吐量。
*   [x] **全链路异步化**: 移除 `src/core/database.py` 中的同步 `create_engine`，统一使用 `AsyncEngine`。
*   [ ] **连接池优化**: 针对 LLM 流式输出和长轮询场景，优化 `asyncpg` / `aiomysql` 连接池参数。

### Phase 2: 状态管理与持久化 (State Persistence)
**目标**: 实现生产级的状态保存与回溯。
*   [ ] **Postgres Checkpointer**: 替换当前的 `SimpleRedisSaver`，使用 Postgres 存储 Checkpoint，支持更复杂的查询。
*   [ ] **TTL 管理**: 自动清理过期的会话状态，防止存储膨胀。

### Phase 3: 可观测性 (Observability)
**目标**: 量化系统性能与成本。
*   [ ] **OpenTelemetry 集成**: 完善 Tracing，追踪每个 Node 的 Token 消耗、耗时和 SQL 执行状态。
*   [ ] **仪表盘**: 接入 Prometheus/Grafana，展示 Agent 成功率、平均响应时间等关键指标。

## 3. 功能增强规划 (Functional Enhancements)

### Feature 1: 动态少样本学习 (Dynamic Few-Shot Learning)
**痛点**: 复杂 Schema 下 Zero-Shot 生成准确率低。
**方案**:
1.  构建 `ExampleSearcher` 向量库。
2.  存储高质量的 `(User Query, Gold SQL)` 对。
3.  运行时检索 Top-K 相似案例注入 Prompt。

### Feature 2: 自动化评估体系 (Automated Evaluation)
**痛点**: 缺乏客观的质量度量。
**方案**:
1.  集成 `Bird` / `Spider` 数据集。
2.  构建 CI/CD 评估脚本，计算 **Execution Accuracy (EX)** 和 **Exact Match (EM)**。

### Feature 3: 交互式自修正 (Interactive Self-Correction)
**痛点**: 错误发生时，Agent 往往陷入死循环。
**方案**:
1.  在前端展示中间 DSL 或 SQL。
2.  允许用户手动修正，Agent 基于修正后的输入重新规划。

## 4. 开发规范 (Development Guidelines)
*   **异步优先**: 新增 I/O 操作必须使用 `async/await`。
*   **类型安全**: 所有新接口必须使用 Pydantic 定义输入输出。
*   **测试驱动**: 修改核心逻辑前，必须补充对应的 `pytest` 用例。
