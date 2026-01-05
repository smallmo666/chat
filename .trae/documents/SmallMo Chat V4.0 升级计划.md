# V4.0 升级计划：暗黑模式与 Python 交互

响应您的“继续升级”指令，我将完成 V3.0 中未实施的 **暗黑模式**，并针对您打开的 `sandbox.py` 文件，升级 Python 分析的交互体验。

## 1. 全局暗黑模式 (Dark Mode)
打造专业、舒适的夜间开发体验。
*   **架构**: 创建 `ThemeContext` 管理主题状态，并持久化到本地存储。
*   **适配**:
    *   **Ant Design**: 使用 AntD 提供的深色算法 (`theme.darkAlgorithm`)。
    *   **Monaco Editor**: 自动切换为 `vs-dark` 主题。
    *   **ECharts**: 自动切换为深色主题。
    *   **自定义组件**: 优化 `ChatWindow`、`SchemaBrowser` 的背景色和文字颜色。

## 2. Python 代码交互 (Interactive Python Playground)
目前 Python 分析是“黑盒”执行，用户无法干预。我们将赋予用户修改分析逻辑的能力。
*   **前端**:
    *   当 Agent 生成 Python 代码时，展示“查看/编辑代码”按钮。
    *   点击后弹出 **Monaco Editor (Python版)**。
    *   允许用户修改代码并点击“重新运行”。
*   **后端**:
    *   利用 `sandbox.py` 中现有的会话保持机制 (`StatefulSandbox`)。
    *   新增 API 接口 `/api/chat/python/execute`，允许在当前会话（已有 DataFrame 上下文）中执行任意 Python 代码并返回结果（文本+图片）。

---

## 实施步骤

1.  **暗黑模式**:
    *   创建 `frontend/src/context/ThemeContext.tsx`。
    *   修改 `App.tsx` 和 `Layout.tsx` 接入主题切换。
    *   全面适配前端组件样式。

2.  **Python 交互后端**:
    *   修改 `src/api/routes/chat.py`，新增 `/python/execute` 接口。
    *   确保接口能复用 `StatefulSandbox` 的 Session。

3.  **Python 交互前端**:
    *   修改 `ChatWindow.tsx`，在 `code_generated` 类型的消息卡片中增加“编辑”按钮。
    *   复用 SQL 审核的 Modal 逻辑，改为支持 Python 编辑和运行。

我将优先实现 **暗黑模式** 以完成视觉升级，随后攻克 **Python 交互**。
