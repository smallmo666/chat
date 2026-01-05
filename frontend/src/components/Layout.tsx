import { Layout, Menu, Grid } from 'antd';
import { 
  ProjectOutlined, 
  DatabaseOutlined, 
  AuditOutlined,
  MenuUnfoldOutlined,
  MenuFoldOutlined,
  BulbOutlined,
  BulbFilled
} from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

const AppLayout = () => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const screens = useBreakpoint();
  const { theme, toggleTheme, isDarkMode } = useTheme();
  
  // Auto collapse on mobile
  useEffect(() => {
      if (!screens.md) {
          setCollapsed(true);
      } else {
          setCollapsed(false);
      }
  }, [screens.md]);

  const menuItems = [
    {
      key: '/projects',
      icon: <ProjectOutlined />,
      label: <Link to="/projects">项目管理</Link>,
    },
    {
      key: '/datasources',
      icon: <DatabaseOutlined />,
      label: <Link to="/datasources">数据源管理</Link>,
    },
    {
      key: '/audit',
      icon: <AuditOutlined />,
      label: <Link to="/audit">审计管理</Link>,
    },
  ];

  const isFullPage = location.pathname.startsWith('/chat/');
  const isMobile = !screens.md;

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        trigger={null} 
        collapsible 
        collapsed={collapsed}
        width={240}
        collapsedWidth={isMobile ? 0 : 80}
        style={{
          boxShadow: '2px 0 8px 0 rgba(29,35,41,.05)',
          zIndex: 100,
          position: isMobile ? 'absolute' : 'relative',
          height: '100vh'
        }}
        zeroWidthTriggerStyle={{ top: 10 }}
      >
        <div className="logo" style={{ 
          height: 64, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)'
        }}>
          <span style={{ 
            color: 'white', 
            fontSize: collapsed ? 16 : 20, 
            fontWeight: 600,
            whiteSpace: 'nowrap',
            transition: 'all 0.2s',
            opacity: collapsed ? 0.7 : 1
          }}>
            {collapsed ? 'DA' : '数据分析智能体'}
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{ borderRight: 0, marginTop: 16 }}
        />
      </Sider>
      <Layout>
        <Header style={{ 
          padding: 0, 
          background: isDarkMode ? '#1f1f1f' : '#fff', 
          display: 'flex', 
          alignItems: 'center',
          boxShadow: isDarkMode ? '0 1px 4px rgba(0,0,0,0.2)' : '0 1px 4px rgba(0,21,41,.08)',
          zIndex: 9,
          height: 64,
          color: isDarkMode ? '#fff' : 'inherit'
        }}>
          <div 
            style={{ 
              padding: '0 24px', 
              cursor: 'pointer',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              fontSize: 18,
              transition: 'color 0.3s'
            }} 
            onClick={() => setCollapsed(!collapsed)}
            className="hover:text-blue-500"
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </div>
          <div style={{ flex: 1 }} />
          
          <div 
            style={{ 
              padding: '0 24px', 
              cursor: 'pointer',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              fontSize: 18,
              transition: 'color 0.3s'
            }} 
            onClick={toggleTheme}
            className="hover:text-blue-500"
          >
            {isDarkMode ? <BulbFilled style={{ color: '#faad14' }} /> : <BulbOutlined />}
          </div>

          {/* Add user profile or actions here if needed */}
        </Header>
        {/* Overlay for mobile sidebar */}
        {isMobile && !collapsed && (
            <div 
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(0,0,0,0.45)',
                    zIndex: 99
                }}
                onClick={() => setCollapsed(true)}
            />
        )}
        <Content
          style={{
            margin: isFullPage ? 0 : (isMobile ? '16px 8px' : '24px 16px'),
            padding: isFullPage ? 0 : (isMobile ? 16 : 24),
            minHeight: 280,
            background: isFullPage ? 'transparent' : '#fff',
            overflow: isFullPage ? 'hidden' : 'auto',
            borderRadius: isFullPage ? 0 : 12,
            boxShadow: isFullPage ? 'none' : '0 1px 2px 0 rgba(0, 0, 0, 0.03)'
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
