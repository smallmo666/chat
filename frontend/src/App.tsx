import React from 'react';
import { ConfigProvider, theme } from 'antd';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/Layout';
import DataSourcePage from './pages/DataSourcePage';
import ProjectPage from './pages/ProjectPage';
import ChatPage from './pages/ChatPage';
import AuditPage from './pages/AuditPage';

const App: React.FC = () => {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/projects" replace />} />
            <Route path="datasources" element={<DataSourcePage />} />
            <Route path="projects" element={<ProjectPage />} />
            <Route path="chat/:projectId" element={<ChatPage />} />
            <Route path="audit" element={<AuditPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
