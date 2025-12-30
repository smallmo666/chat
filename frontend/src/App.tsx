import React from 'react';
import { ConfigProvider, theme, App as AntdApp } from 'antd';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import AppLayout from './components/Layout';
import DataSourcePage from './pages/DataSourcePage';
import ProjectPage from './pages/ProjectPage';
import ChatPage from './pages/ChatPage';
import AuditPage from './pages/AuditPage';
import LoginPage from './pages/LoginPage';
import SettingsPage from './pages/SettingsPage';
import { AuthProvider, useAuth } from './context/AuthContext';

// Protected Route Component
const ProtectedRoute = () => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) return null; // Or a spinner
  
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

const AppRoutes = () => {
    return (
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          
          <Route element={<ProtectedRoute />}>
              <Route path="/" element={<AppLayout />}>
                <Route index element={<Navigate to="/projects" replace />} />
                <Route path="datasources" element={<DataSourcePage />} />
                <Route path="projects" element={<ProjectPage />} />
                <Route path="chat/:projectId" element={<ChatPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
          </Route>
        </Routes>
    )
}

const App: React.FC = () => {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 10,
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
          colorBgContainer: '#ffffff',
        },
        components: {
          Layout: {
            bodyBg: '#f5f7fa',
            headerBg: '#ffffff',
            siderBg: '#001529',
          },
          Card: {
            borderRadiusLG: 12,
            boxShadowTertiary: '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
          },
          Button: {
            borderRadius: 8,
            controlHeight: 36,
          },
          Input: {
            controlHeight: 36,
            borderRadius: 8,
          }
        }
      }}
    >
      <BrowserRouter>
        <AntdApp>
            <AuthProvider>
                <AppRoutes />
            </AuthProvider>
        </AntdApp>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
