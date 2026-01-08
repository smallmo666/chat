import React from 'react';
import { Card, Typography, Space, theme } from 'antd';
import { RobotOutlined, ThunderboltOutlined, TableOutlined, BarChartOutlined, CompassOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

interface WelcomeScreenProps {
    onSampleClick: (text: string) => void;
    isDarkMode?: boolean;
    projectName?: string;
}

const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onSampleClick, isDarkMode, projectName }) => {
    const { token } = theme.useToken();
    
    const samples = [
        { 
            icon: <ThunderboltOutlined style={{ color: '#faad14' }} />, 
            title: '快速统计', 
            desc: '统计上个月的订单总量',
            query: '统计上个月的订单总量'
        },
        { 
            icon: <BarChartOutlined style={{ color: '#52c41a' }} />, 
            title: '趋势分析', 
            desc: '分析最近半年的用户增长趋势',
            query: '分析最近半年的用户增长趋势'
        },
        { 
            icon: <TableOutlined style={{ color: '#1677ff' }} />, 
            title: '数据查询', 
            desc: '查询销售额最高的前10个商品',
            query: '查询销售额最高的前10个商品'
        },
        { 
            icon: <CompassOutlined style={{ color: '#722ed1' }} />, 
            title: '异常检测', 
            desc: '找出上周退款率异常高的产品',
            query: '找出上周退款率异常高的产品'
        }
    ];

    return (
        <div style={{ 
            height: '100%', 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center',
            padding: '0 20px 100px',
            color: 'var(--text-primary)',
            animation: 'fadeIn 0.6s ease-out'
        }}>
            <div style={{ 
                width: 96, 
                height: 96, 
                background: `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryActive} 100%)`, 
                borderRadius: '32px', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center', 
                marginBottom: 32,
                boxShadow: `0 20px 40px -10px ${token.colorPrimary}60`,
                transform: 'rotate(-5deg)',
                transition: 'transform 0.3s ease'
            }}
            className="hero-icon"
            >
                <RobotOutlined style={{ color: 'white', fontSize: 48 }} />
            </div>
            
            <Title level={2} style={{ marginBottom: 12, color: 'var(--text-primary)', textAlign: 'center' }}>
                {projectName ? `欢迎使用 ${projectName}` : '智能数据助手'}
            </Title>
            <Paragraph style={{ fontSize: 16, color: 'var(--text-secondary)', marginBottom: 48, textAlign: 'center', maxWidth: 560, lineHeight: 1.6 }}>
                我可以帮您查询数据库、分析业务趋势、生成可视化报表。
                <br />
                请直接用自然语言告诉我您想了解什么。
            </Paragraph>

            <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', 
                gap: 20, 
                width: '100%', 
                maxWidth: 900 
            }}>
                {samples.map((item, idx) => (
                    <Card 
                        key={idx}
                        hoverable 
                        className="welcome-card"
                        style={{ 
                            background: 'var(--bg-container)', 
                            borderColor: 'var(--border-color)',
                            borderRadius: 'var(--radius-lg)',
                            boxShadow: 'var(--shadow-sm)',
                            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                        }}
                        onClick={() => onSampleClick(item.query)}
                    >
                        <Space align="start" size={16}>
                            <div style={{ 
                                width: 48,
                                height: 48,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: isDarkMode ? 'rgba(255,255,255,0.05)' : '#f5f7fa', 
                                borderRadius: '14px',
                                fontSize: 24,
                                transition: 'transform 0.3s ease'
                            }} className="card-icon">
                                {item.icon}
                            </div>
                            <div>
                                <Text strong style={{ fontSize: 16, display: 'block', color: 'var(--text-primary)', marginBottom: 4 }}>{item.title}</Text>
                                <Text type="secondary" style={{ fontSize: 13, lineHeight: 1.5 }}>{item.desc}</Text>
                            </div>
                        </Space>
                    </Card>
                ))}
            </div>
            
            <style>{`
                .hero-icon:hover {
                    transform: rotate(0deg) scale(1.05) !important;
                }
                .welcome-card:hover {
                    transform: translateY(-4px);
                    box-shadow: var(--shadow-md) !important;
                    border-color: ${token.colorPrimary}40 !important;
                }
                .welcome-card:hover .card-icon {
                    transform: scale(1.1);
                    background: ${token.colorPrimaryBg} !important;
                }
            `}</style>
        </div>
    );
};

export default WelcomeScreen;
