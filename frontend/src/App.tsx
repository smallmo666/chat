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
import KnowledgePage from './pages/KnowledgePage';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider, useTheme } from './context/ThemeContext';

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
                <Route path="knowledge" element={<KnowledgePage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
          </Route>
        </Routes>
    )
}

const AppContent: React.FC = () => {
  const { theme: currentTheme, isDarkMode } = useTheme();

  return (
    <ConfigProvider
      theme={{
        algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 10,
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
          colorBgContainer: isDarkMode ? '#1f1f1f' : '#ffffff',
          colorBgLayout: isDarkMode ? '#141414' : '#f5f7fa',
        },
        components: {
          Layout: {
            bodyBg: isDarkMode ? '#141414' : '#f5f7fa',
            headerBg: isDarkMode ? '#1f1f1f' : '#ffffff',
            siderBg: '#001529', // Keep sider dark for now
          },
          Card: {
            borderRadiusLG: 12,
            boxShadowTertiary: isDarkMode ? 'none' : '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
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

const App: React.FC = () => {
    return (
        <ThemeProvider>
            <AppContent />
        </ThemeProvider>
    );
};

export default App;
