import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, App, Tabs } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, DatabaseOutlined } from '@ant-design/icons';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const { Title } = Typography;

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('login');
  const { message } = App.useApp();

  const onLogin = async (values: any) => {
    setLoading(true);
    try {
      // OAuth2PasswordRequestForm expects form data, not JSON
      const formData = new FormData();
      formData.append('username', values.username);
      formData.append('password', values.password);
      
      const response = await api.post('/api/auth/login', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      await login(response.data.access_token);
      message.success('Login successful!');
      navigate('/');
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const onRegister = async (values: any) => {
      setLoading(true);
      try {
        await api.post('/api/auth/register', values);
        message.success('Registration successful! Please login.');
        setActiveTab('login');
      } catch (error: any) {
        message.error(error.response?.data?.detail || 'Registration failed');
      } finally {
        setLoading(false);
      }
  };

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      height: '100vh', 
      background: 'linear-gradient(135deg, #e0f7fa 0%, #e3f2fd 50%, #f3e5f5 100%)', // Softer, friendlier gradient
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Decorative Background Elements */}
      <div style={{
          position: 'absolute',
          top: -100,
          right: -100,
          width: 400,
          height: 400,
          background: 'radial-gradient(circle, rgba(64,169,255,0.2) 0%, rgba(0,0,0,0) 70%)',
          borderRadius: '50%',
          filter: 'blur(40px)',
          zIndex: 0
      }} />
      <div style={{
          position: 'absolute',
          bottom: -50,
          left: -50,
          width: 300,
          height: 300,
          background: 'radial-gradient(circle, rgba(149,222,100,0.2) 0%, rgba(0,0,0,0) 70%)',
          borderRadius: '50%',
          filter: 'blur(40px)',
          zIndex: 0
      }} />

      <Card 
        style={{ 
          width: 440, 
          boxShadow: '0 12px 32px rgba(0,0,0,0.08)', 
          borderRadius: 24,
          border: '1px solid rgba(255,255,255,0.6)',
          backdropFilter: 'blur(20px)',
          background: 'rgba(255, 255, 255, 0.85)',
          zIndex: 1
        }}
        styles={{ body: { padding: '48px 40px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
           <div style={{ 
               width: 64, height: 64, margin: '0 auto 24px', 
               background: 'linear-gradient(135deg, #1677ff 0%, #69b1ff 100%)',
               borderRadius: 16,
               display: 'flex', alignItems: 'center', justifyContent: 'center',
               boxShadow: '0 8px 16px rgba(22,119,255,0.2)'
           }}>
               <DatabaseOutlined style={{ fontSize: 32, color: '#fff' }} />
           </div>
           <Title level={2} style={{ color: '#001529', marginBottom: 8, fontWeight: 700, letterSpacing: '-0.5px' }}>数据分析智能体</Title>
           <Typography.Text type="secondary" style={{ fontSize: 16 }}>新一代企业级智能数据洞察平台</Typography.Text>
        </div>
        
        <Tabs 
            activeKey={activeTab} 
            onChange={setActiveTab} 
            centered 
            items={[
            {
                key: 'login',
                label: '账号登录',
                children: (
                    <Form
                      name="login"
                      initialValues={{ remember: true }}
                      onFinish={onLogin}
                      layout="vertical"
                      size="large"
                      style={{ marginTop: 24 }}
                    >
                      <Form.Item
                        name="username"
                        rules={[{ required: true, message: '请输入用户名' }]}
                      >
                        <Input 
                            prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} 
                            placeholder="用户名" 
                            style={{ borderRadius: 12, background: '#f5f7fa', border: '1px solid #e8e8e8' }}
                        />
                      </Form.Item>
                      <Form.Item
                        name="password"
                        rules={[{ required: true, message: '请输入密码' }]}
                      >
                        <Input.Password 
                            prefix={<LockOutlined style={{ color: '#bfbfbf' }} />} 
                            placeholder="密码" 
                            style={{ borderRadius: 12, background: '#f5f7fa', border: '1px solid #e8e8e8' }}
                        />
                      </Form.Item>
                      <Form.Item style={{ marginTop: 32 }}>
                        <Button 
                            type="primary" 
                            htmlType="submit" 
                            block 
                            size="large" 
                            loading={loading}
                            style={{ 
                                height: 48, 
                                borderRadius: 12, 
                                fontSize: 16, 
                                fontWeight: 600,
                                background: 'linear-gradient(90deg, #1677ff 0%, #4096ff 100%)',
                                border: 'none',
                                boxShadow: '0 4px 12px rgba(22,119,255,0.3)'
                            }}
                        >
                          立即登录
                        </Button>
                      </Form.Item>
                    </Form>
                )
            },
            {
                key: 'register',
                label: '快速注册',
                children: (
                    <Form
                      name="register"
                      onFinish={onRegister}
                      layout="vertical"
                      size="large"
                      style={{ marginTop: 24 }}
                    >
                      <Form.Item
                        name="username"
                        rules={[{ required: true, message: '请设置用户名' }]}
                      >
                        <Input 
                            prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} 
                            placeholder="设置用户名" 
                            style={{ borderRadius: 12, background: '#f5f7fa', border: '1px solid #e8e8e8' }}
                        />
                      </Form.Item>
                       <Form.Item
                        name="email"
                        rules={[{ type: 'email', message: '邮箱格式不正确' }]}
                      >
                        <Input 
                            prefix={<MailOutlined style={{ color: '#bfbfbf' }} />} 
                            placeholder="绑定邮箱 (选填)" 
                            style={{ borderRadius: 12, background: '#f5f7fa', border: '1px solid #e8e8e8' }}
                        />
                      </Form.Item>
                      <Form.Item
                        name="password"
                        rules={[{ required: true, message: '请设置密码' }]}
                      >
                        <Input.Password 
                            prefix={<LockOutlined style={{ color: '#bfbfbf' }} />} 
                            placeholder="设置密码" 
                            style={{ borderRadius: 12, background: '#f5f7fa', border: '1px solid #e8e8e8' }}
                        />
                      </Form.Item>
                      <Form.Item style={{ marginTop: 32 }}>
                        <Button 
                            type="primary" 
                            htmlType="submit" 
                            block 
                            size="large" 
                            loading={loading}
                            style={{ 
                                height: 48, 
                                borderRadius: 12, 
                                fontSize: 16, 
                                fontWeight: 600,
                                background: 'linear-gradient(90deg, #52c41a 0%, #95de64 100%)',
                                border: 'none',
                                boxShadow: '0 4px 12px rgba(82,196,26,0.3)'
                            }}
                        >
                          注册账号
                        </Button>
                      </Form.Item>
                    </Form>
                )
            }
        ]} />

      </Card>
    </div>
  );
};

export default LoginPage;
