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
          height: '100vh',
          display: 'flex',
          flexDirection: 'column'
        }}
        zeroWidthTriggerStyle={{ top: 10 }}
      >
        <div className="logo" style={{ 
          height: 64, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          flexShrink: 0
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
        
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
            <Menu
              theme="dark"
              mode="inline"
              selectedKeys={[location.pathname]}
              items={menuItems}
              style={{ borderRight: 0, marginTop: 16 }}
            />
        </div>

        {/* Sider Footer Actions */}
        <div style={{ 
            padding: '16px 0', 
            borderTop: '1px solid rgba(255,255,255,0.1)',
            display: 'flex',
            flexDirection: collapsed ? 'column' : 'row',
            alignItems: 'center',
            justifyContent: 'space-around',
            gap: 8,
            color: 'rgba(255,255,255,0.65)'
        }}>
             <div 
                style={{ cursor: 'pointer', padding: 8, borderRadius: 4, transition: 'all 0.3s' }}
                className="hover:bg-white/10 hover:text-white"
                onClick={() => setCollapsed(!collapsed)}
                title={collapsed ? "展开菜单" : "折叠菜单"}
             >
                {collapsed ? <MenuUnfoldOutlined style={{ fontSize: 18 }} /> : <MenuFoldOutlined style={{ fontSize: 18 }} />}
             </div>
             
             <div 
                style={{ cursor: 'pointer', padding: 8, borderRadius: 4, transition: 'all 0.3s' }}
                className="hover:bg-white/10 hover:text-white"
                onClick={toggleTheme}
                title="切换主题"
             >
                {isDarkMode ? <BulbFilled style={{ color: '#faad14', fontSize: 18 }} /> : <BulbOutlined style={{ fontSize: 18 }} />}
             </div>
        </div>
      </Sider>
      <Layout>
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
            margin: 0,
            padding: 0,
            height: '100vh', // Full height
            overflow: 'hidden', // Content manages its own scroll
            background: isFullPage ? 'transparent' : '#f0f2f5',
            position: 'relative'
          }}
        >
          {/* Apply padding/margin only for non-full pages inside the content container if needed, 
              but since ChatPage handles its own layout, we keep it simple here. 
              For other pages, we might want a wrapper, but let's stick to the requested clean layout.
          */}
          <div style={{ 
              height: '100%', 
              overflow: isFullPage ? 'hidden' : 'auto',
              padding: isFullPage ? 0 : (isMobile ? 16 : 24)
          }}>
              <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
