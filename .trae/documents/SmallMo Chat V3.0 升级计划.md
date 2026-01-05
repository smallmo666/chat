# 修复与 V3.0 升级计划

检测到 `remark-gfm` 依赖丢失，且上一步安装的 `@monaco-editor/react` 可能未正确写入 `package.json`。我将优先修复环境问题，然后继续执行 V3.0 升级。

## 1. 环境修复 (Fix Dependencies)
*   **执行**: `npm install` (确保所有依赖被安装)
*   **补充安装**: 再次执行 `npm install @monaco-editor/react remark-gfm` 以确保它们被显式加入依赖列表。

## 2. 语音交互 (Voice Interaction)
*   **前端**: 修改 `ChatWindow.tsx`。
    *   引入 `SpeechRecognition` (Web API)。
    *   添加麦克风按钮。
    *   实现：按住说话 -> 识别文本 -> 填充输入框。

## 3. 聊天记录导出 (Export Chat History)
*   **前端**: 修改 `ChatWindow.tsx`。
    *   添加“导出记录”按钮。
    *   实现 `exportToMarkdown` 函数，将对话历史转换为 Markdown 文件下载。

## 4. 全局暗黑模式 (Dark Mode) - *可选，视进度而定*
*   **前端**: 搭建 `ThemeContext` 和切换开关。

我将首先执行依赖修复，确保项目可运行，然后实现语音和导出功能。
