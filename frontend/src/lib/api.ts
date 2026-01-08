import axios from 'axios';
import type { ChatSession } from '../chatTypes';

const API_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to add JWT token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor to handle 401 (Logout)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const url: string = error.config?.url || '';
      const isAuthMe = url.includes('/auth/me');
      localStorage.removeItem('token');
      if (!isAuthMe) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Session Management API
export const fetchSessions = async (projectId: number): Promise<ChatSession[]> => {
    const response = await api.post<ChatSession[]>('/api/chat/sessions/list', { project_id: projectId });
    return response.data;
};

export const fetchSessionHistory = async (sessionId: string): Promise<any[]> => {
    const response = await api.post<any[]>('/api/chat/sessions/history', { session_id: sessionId });
    return response.data;
};

export const deleteSession = async (sessionId: string) => {
    return await api.post('/api/chat/sessions/delete', { session_id: sessionId });
};

export const updateSessionTitle = async (sessionId: string, title: string) => {
    return await api.post('/api/chat/sessions/update', { session_id: sessionId, title });
};

// Project API
export const fetchProject = async (id: number) => {
    const response = await api.post('/api/projects/get', { id });
    return response.data;
};

export default api;
