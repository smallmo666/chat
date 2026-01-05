# V2.0 深度升级计划

我将在现有的基础上进行三个方向的深度升级：**智能分析报告 (Smart Analysis Report)**、**专业级 SQL 编辑器 (Professional SQL Editor)** 和 **Schema 拖拽交互 (Drag-and-Drop Schema)**。

## 1. 智能分析报告 (Smart Analysis Report)
用户进行了一系列对话后，可能希望将所有分析结果汇总成一份报告。
*   **后端**: 扩展 `ui_artist_node`，增加一个新的模式 `report`。如果检测到用户意图是“生成报告”或“总结”，则生成一份包含富文本、图表和关键指标的长篇 React 组件。
*   **前端**: 在聊天窗口顶部增加“生成报告”按钮（目前作为 Demo，先通过对话触发）。支持渲染长篇报告组件。

## 2. 专业级 SQL 编辑器集成
目前的 SQL 审核和编辑仅使用了简单的 `TextArea`，体验较差。
*   **前端**: 引入 `@monaco-editor/react`。
*   **交互**: 在“SQL 审核”弹窗中，使用 Monaco Editor 替换 TextArea，提供 SQL 语法高亮和简单的自动补全。

## 3. Schema 拖拽交互优化
允许用户直接操作左侧的 Schema 树，将表名拖入对话框。
*   **前端**: 修改 `SchemaBrowser`，启用 AntD Tree 的 `draggable` 属性。
*   **前端**: 修改 `ChatWindow` 的输入框，使其能够接收拖拽事件，并插入表名。

---

## 实施步骤

1.  **SQL 编辑器升级**:
    *   安装 `@monaco-editor/react`。
    *   在 `ChatWindow.tsx` 中引入并替换 `TextArea` (仅用于 SQL 审核 Modal)。

2.  **Schema 拖拽**:
    *   修改 `SchemaBrowser.tsx`，支持拖拽节点。
    *   修改 `ChatWindow.tsx`，监听 `onDrop` 事件。

3.  **智能报告生成**:
    *   修改 `artist.py`，增加 `REPORT_PROMPT`，用于生成类似“分析简报”的 React 组件。
    *   在 `ChatWindow.tsx` 中增加一个快捷指令按钮“生成本轮分析报告”。

由于时间有限，我将优先保证 **SQL 编辑器** 和 **拖拽交互** 的落地，因为它们对交互体验提升最直接。
