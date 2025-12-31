# Text2SQL 智能体项目升级与改进方案

本文档基于当前代码库的深度分析，提出了一套从功能增强、架构演进到工程化落地的完整改进路线图。旨在将现有的原型系统升级为**企业级、自适应、高安全**的智能数据分析平台。

## 1. 核心功能增强 (Intelligence & Capabilities)

### 1.1 主动学习与反馈闭环 (RLHF Loop)
目前系统仅具备被动的 Few-Shot 检索，缺乏从实际使用中学习的能力。
*   **显式反馈机制**: 
    *   在 API 层增加 `/feedback` 接口，支持用户对 SQL 执行结果进行“点赞（Thumbs Up）”或“修正（Correction）”。
    *   前端允许用户直接编辑生成的 SQL 并重新运行。
*   **自动进化 (Auto-Evolution)**:
    *   **正向增强**: 当用户手动修正 SQL 并成功执行后，系统应自动将 `{User Query, Corrected SQL}` 作为高质量样本存入 `FewShotRetriever` 的向量库。
    *   **负向规避**: 记录执行失败或用户标记为错误的 Case，构建“错题本”。在 Prompt 中动态注入“避坑指南”，提示模型“注意：上次在类似问题上犯过 X 错误，请避免”。

### 1.2 深度多轮对话与意图理解
*   **槽位填充 (Slot Filling)**: 
    *   引入独立的对话状态追踪（Dialogue State Tracking, DST）模块。
    *   识别查询中的关键实体槽位（如 `TimeRange`, `Region`, `ProductCategory`）。
    *   当信息缺失时，`ClarifyIntent` 节点不再是泛泛而谈，而是能精确反问：“请问您是指**哪个时间段**的数据？”
*   **指代消解 (Coreference Resolution)**:
    *   增强上下文重写逻辑，引入专门的 NLP 模型处理复杂的代词指代（如“它们”、“上个月的那个异常值”），确保多轮对话的流畅性。

### 1.3 异构数据源融合 (RAG + SQL)
*   **非结构化知识融合**: 
    *   许多业务问题（如“为什么上个月销售额下降？”）无法仅靠 SQL 数据回答。
    *   **方案**: 引入文档 RAG 模块，索引业务周报、Wiki 或元数据文档。系统首先判断问题类型，如果是归因分析，则结合 SQL 数据（事实）和文档检索（原因）生成综合回答。
*   **跨库查询 (Federated Query)**:
    *   升级数据层，支持跨多个数据库实例的查询，或引入 **Trino/Presto** 作为统一查询引擎，屏蔽底层数据源的异构性。

## 2. 架构演进 (Architecture Evolution)

### 2.1 沙箱环境容器化 (Containerization)
*   **现状风险**: 目前使用进程内 `StatefulSandbox`，依赖 AST 静态检查。虽然轻量，但难以完全防御复杂的攻击（如通过 C 扩展库绕过），且无法安全支持第三方库安装。
*   **改进方案**: 
    *   **Docker / Firecracker**: 为每个 Session 启动一个独立的、瞬时的轻量级容器。
    *   **网络隔离**: 容器内仅允许访问必要的 API 网关，彻底隔离宿主机文件系统。
    *   **依赖管理**: 允许用户动态 `pip install` 需要的分析库（如 `prophet`, `scikit-learn`），大幅增强分析能力。

### 2.2 存算分离与微服务化
*   **独立分析服务**: 
    *   随着数据量和分析复杂度的增加，Python 分析节点将成为 CPU 密集型瓶颈，影响 API 响应速度。
    *   **方案**: 将 `PythonAnalysis` 节点拆分为独立微服务，通过 gRPC 或消息队列（Kafka/RabbitMQ）与主流程异步交互。
*   **向量库独立部署**:
    *   目前使用本地文件版 ChromaDB。生产环境建议迁移至 **ChromaDB Server** 模式或 **Milvus**，支持分布式部署、数据持久化备份和海量向量的高效检索。

## 3. 工程化与运维 (Engineering & DevOps)

### 3.1 自动化评估流水线 (Evaluation Pipeline)
*   **基准测试集 (Benchmark)**: 建立基于真实业务数据的 Golden Dataset（包含 Query-SQL 对）。
*   **CI/CD 集成**: 
    *   每次 Prompt 修改、模型升级或代码提交时，自动触发评估脚本。
    *   **核心指标**: 计算 **执行准确率 (Execution Accuracy)**（结果一致性）和 **逻辑匹配率 (Exact Match)**（SQL 结构相似度）。
    *   **回归测试**: 确保新版本不会导致以前能答对的问题变错。

### 3.2 全链路可观测性 (Observability)
*   **业务监控**: 基于 OpenTelemetry 和 Prometheus，监控核心业务指标：
    *   SQL 生成成功率
    *   平均端到端延迟
    *   Token 消耗与成本预估
    *   缓存命中率
*   **Trace 深度集成**: 记录每个 Graph 节点（Planner, GenDSL, ExecuteSQL）的输入输出快照 (Trace Span)，便于在 Jaeger/Zipkin 中可视化调用链路，快速定位坏例根因。

### 3.3 数据治理辅助
*   **Schema 自动同步**: 
    *   开发定时任务或监听数据库 DDL 变更事件。
    *   当数据库表结构发生变化时，自动更新 `SchemaSearcher` 的向量索引，确保智能体始终掌握最新的元数据，消除“幻觉”风险。
