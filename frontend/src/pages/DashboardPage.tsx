import React, { useState } from 'react';
import { Layout, Typography, Card, Empty, Button, message, Popconfirm } from 'antd';
import { DeleteOutlined, DashboardOutlined, PushpinOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';

const { Content } = Layout;
const { Title } = Typography;

interface PinnedChart {
    id: string;
    title: string;
    option: any;
    timestamp: number;
}

const DashboardPage: React.FC = () => {
    const [charts, setCharts] = useState<PinnedChart[]>(() => {
        try {
            const saved = localStorage.getItem('pinned_charts');
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            return [];
        }
    });

    const removeChart = (id: string) => {
        const newCharts = charts.filter(c => c.id !== id);
        setCharts(newCharts);
        localStorage.setItem('pinned_charts', JSON.stringify(newCharts));
        message.success('图表已从看板移除');
    };

    return (
        <Layout style={{ height: '100%', background: '#f0f2f5' }}>
            <Content style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24 }}>
                    <DashboardOutlined style={{ fontSize: 24, marginRight: 12, color: '#1677ff' }} />
                    <Title level={3} style={{ margin: 0 }}>数据看板</Title>
                </div>

                {charts.length === 0 ? (
                    <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="暂无收藏的图表"
                    >
                        <Button type="primary" href="/chat">去对话生成图表</Button>
                    </Empty>
                ) : (
                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', 
                        gap: '24px' 
                    }}>
                        {charts.map(chart => (
                            <Card 
                                key={chart.id} 
                                title={chart.title} 
                                extra={
                                    <Popconfirm title="确定移除?" onConfirm={() => removeChart(chart.id)}>
                                        <Button type="text" icon={<DeleteOutlined />} danger />
                                    </Popconfirm>
                                }
                                style={{ borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}
                            >
                                <ReactECharts option={chart.option} style={{ height: 300 }} theme="macarons" />
                                <div style={{ marginTop: 12, fontSize: 12, color: '#999', textAlign: 'right' }}>
                                    {new Date(chart.timestamp).toLocaleString()}
                                </div>
                            </Card>
                        ))}
                    </div>
                )}
            </Content>
        </Layout>
    );
};

export default DashboardPage;
