// 应用程序配置
// 优先使用环境变量 VITE_API_BASE_URL，否则根据模式回退
const getApiBaseUrl = () => {
    if (import.meta.env.VITE_API_BASE_URL) {
        return import.meta.env.VITE_API_BASE_URL;
    }
    // 生产环境通常使用相对路径 /api (由 Nginx 代理)
    if (import.meta.env.PROD) {
        return '/api';
    }
    // 开发环境默认
    return 'http://localhost:8000/api';
};

export const API_BASE_URL = getApiBaseUrl();

export const ENDPOINTS = {
    CHAT: `${API_BASE_URL}/chat`,
    SCHEMA: `${API_BASE_URL}/schema`, // 假设有 schema 接口
};
