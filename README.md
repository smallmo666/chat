# Enterprise Text2SQL Agent

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-blue.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

本项目是一个企业级的高级 Text2SQL 智能体系统，旨在通过自然语言与数据库进行交互。采用 **LangGraph** 驱动的 **Planner-Supervisor-Worker** 架构，集成了 **异步执行**、**安全防护**、**实体链接** 和 **Python 代码解释器** 等高级特性，能够从容应对复杂的企业级数据分析需求。

## 🌟 核心特性 (Key Features)

### 1. 🧠 深度智能
- **动态规划 (Dynamic Planning)**: 不仅仅是翻译 SQL，而是先生成执行计划（查表 -> 生成 DSL -> 转 SQL -> Python 分析 -> 绘图），支持复杂多步任务。
- **实体链接 (Entity Linking)**: 内置 `ValueSearcher`，自动纠正用户输入的模糊实体（如 "iPhone 15" -> "Apple iPhone 15 Pro Max"），显著提升查询准确率。
- **Python 代码解释器 (Data Agent)**: 超越 SQL！对于预测、复杂统计或高级清洗任务，自动编写并执行 Python (`pandas`) 代码进行分析。

### 2. ⚡ 高性能架构
- **全链路异步 (Async I/O)**: 数据库执行层采用 `asyncpg` / `aiomysql`，配合 FastAPI 的异步特性，在高并发下保持极低延迟。
- **数据库连接池 (Pooling)**: 智能管理多租户连接池，复用 SQLAlchemy Engine，避免资源泄露。
- **并行执行**: 分析与可视化任务并行处理，减少用户等待时间。

### 3. 🛡️ 企业级安全
- **SQL 防护墙 (Guardrails)**: 严格的正则白名单/黑名单机制，强制拦截 DDL/DML (DROP, DELETE, UPDATE) 及多语句注入攻击。
- **沙箱执行 (Sandbox)**: Python 代码在受限环境中运行，屏蔽危险系统调用。
- **全链路审计 (Audit Logging)**: 记录每一次交互的完整生命周期（Prompt, Plan, SQL, Result, Error），满足合规性要求。

### 4. 📊 交互体验
- **流式响应 (SSE)**: 实时推送思考过程 (Thinking)、执行步骤 (Steps) 和增量结果。
- **智能可视化**: 自动生成 ECharts 图表，支持动态交互。
- **Schema 智能剪枝**: 基于 RAG 技术动态检索相关表结构，支持 1000+ 表的大规模数据库。

## 🏗️ 系统架构

### 架构模式：Planner-Supervisor-Worker
本项目基于 LangGraph 构建了一个有向无环图（DAG）工作流。

```mermaid
graph TD
    START --> Planner
    Planner --> Supervisor
    Supervisor --> |Next Step| Nodes
    Nodes --> Supervisor
    Supervisor --> |Plan Finished| END

    subgraph Nodes [Worker Nodes]
        ClarifyIntent[意图澄清]
        SelectTables[表选择 (RAG)]
        GenerateDSL[生成 DSL]
        DSLtoSQL[SQL 编译]
        ExecuteSQL[SQL 执行 (Async)]
        PythonAnalysis[Python 分析]
        Visualization[可视化生成]
        TableQA[表结构问答]
    end
```

### 核心模块
| 模块 | 职责 | 关键技术 |
| :--- | :--- | :--- |
| **Planner** | 生成分步执行计划 | Prompt Engineering |
| **SelectTables** | 检索相关表结构 | ChromaDB, Embedding |
| **DSLtoSQL** | 生成 SQL 并修正值 | Entity Linking (ValueSearcher) |
| **ExecuteSQL** | 执行 SQL | Async SQLAlchemy, Security Guardrails |
| **PythonAnalysis**| 高级数据分析 | Pandas, Sandbox |
| **Audit** | 审计日志记录 | SQLModel, Async IO |

## 🚀 快速启动

### 1. 环境准备
确保已安装 Python 3.13+ 和 Node.js 18+。

### 2. 后端启动
```bash
# 1. 安装依赖 (使用 uv 包管理器)
uv sync

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库配置

# 3. 启动服务
uv run uvicorn src.server:app --reload
```

### 3. 前端启动
```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
```
访问 `http://localhost:5173` 即可开始使用。

## 🧪 测试与验证

项目包含完善的单元测试，特别是针对安全模块。

```bash
# 运行安全测试
uv run python tests/test_sql_safety.py
```

## 📂 目录结构
```
.
├── frontend/           # React 前端项目
├── src/
│   ├── agents/         # LangGraph Agents (Planner, SQL, Python, etc.)
│   ├── state/          # 状态定义
│   ├── utils/          # 核心工具 (DB, Security, Sandbox, ValueSearch)
│   ├── graph.py        # 图构建
│   └── server.py       # FastAPI 服务入口
├── tests/              # 测试套件
└── pyproject.toml      # 依赖配置
```

## � 配置指南 (.env)

```ini
# 应用数据库 (元数据/审计)
APP_DB_HOST=localhost
APP_DB_PORT=5432
APP_DB_USER=postgres
APP_DB_PASSWORD=secret
APP_DB_NAME=text2sql_app

# 默认查询数据库 (业务数据)
QUERY_DB_HOST=localhost
QUERY_DB_PORT=5432
QUERY_DB_USER=postgres
QUERY_DB_PASSWORD=secret
QUERY_DB_NAME=demo_db

# 模型配置
MODEL_NAME=qwen-max
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
```
