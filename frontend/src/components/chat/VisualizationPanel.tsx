import React, { useEffect, useRef } from 'react';
import { Card, Space, Button } from 'antd';
import { ReloadOutlined, DownloadOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';

interface VisualizationPanelProps {
    config: any;
    onUpdateConfig?: (config: any) => void;
}

const VisualizationPanel: React.FC<VisualizationPanelProps> = ({ config }) => {
    const chartRef = useRef<HTMLDivElement>(null);
    const chartInstance = useRef<ReturnType<typeof echarts.init> | null>(null);

    useEffect(() => {
        if (!chartRef.current || !config) return;

        // Init chart
        if (!chartInstance.current) {
            chartInstance.current = echarts.init(chartRef.current);
        }

        // Set options
        try {
            chartInstance.current.setOption(config);
        } catch (e) {
            console.error("Failed to render chart:", e);
        }

        // Resize handler
        const handleResize = () => chartInstance.current?.resize();
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chartInstance.current?.dispose();
            chartInstance.current = null;
        };
    }, [config]);

    return (
        <Card 
            size="small" 
            style={{ marginTop: 16, border: '1px solid var(--border-color)' }}
            title={
                <Space>
                    <span>数据可视化</span>
                </Space>
            }
            extra={
                <Space>
                    <Button type="text" icon={<ReloadOutlined />} size="small" />
                    <Button type="text" icon={<DownloadOutlined />} size="small" />
                </Space>
            }
        >
            <div ref={chartRef} style={{ width: '100%', height: 300 }} />
        </Card>
    );
};

export default VisualizationPanel;
