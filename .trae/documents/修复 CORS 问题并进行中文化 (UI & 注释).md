I will fix the CORS error and localize the UI/Code comments as requested.

### 1. Fix "Failed to load data" (CORS Issue)
*   **Root Cause**: FastAPI's `CORSMiddleware` is configured with `allow_origins=["*"]` and `allow_credentials=True`. This combination is invalid in modern browsers.
*   **Action**: In `src/server.py`, change `allow_credentials=True` to `allow_credentials=False` to be compatible with wildcard origins.

### 2. Localization (Chinese Translation)
*   **Frontend UI**:
    *   `src/pages/ProjectPage.tsx`: Translate table headers ("Name" -> "项目名称", "Data Source" -> "数据源", "Action" -> "操作"), buttons, and messages.
    *   `src/pages/DataSourcePage.tsx`: Translate table headers ("Host" -> "主机", "Port" -> "端口", etc.) and form labels.
    *   `src/pages/AuditPage.tsx`: Translate table headers ("Session" -> "会话ID", "Query" -> "查询内容", "Status" -> "状态", "Duration" -> "耗时", "Time" -> "时间").
*   **Code Comments**:
    *   Translate comments in `src/pages/ProjectPage.tsx` and `src/server.py` to Chinese to match the codebase style.

### 3. Verification
*   Restart the backend server.
*   Verify the frontend loads data without CORS errors.
*   Confirm all UI elements are in Chinese.
