import React from 'react';
import { Card, Button, Typography, Space } from 'antd';
import { DownloadOutlined, FileExcelOutlined, FileTextOutlined } from '@ant-design/icons';

interface DataDownloadCardProps {
    token: string;
}

const DataDownloadCard: React.FC<DataDownloadCardProps> = ({ token }) => {
    const handleDownload = (format: 'csv' | 'excel') => {
        // Implement download logic using token
        window.open(`/api/download?token=${token}&format=${format}`, '_blank');
    };

    return (
        <Card size="small" style={{ marginTop: 12, background: 'var(--bg-container-light)' }}>
            <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <DownloadOutlined style={{ color: 'var(--primary-color)' }} />
                    <Typography.Text strong>数据导出准备就绪</Typography.Text>
                </div>
                <Space>
                    <Button 
                        size="small" 
                        icon={<FileTextOutlined />} 
                        onClick={() => handleDownload('csv')}
                    >
                        下载 CSV
                    </Button>
                    <Button 
                        size="small" 
                        icon={<FileExcelOutlined />} 
                        onClick={() => handleDownload('excel')}
                    >
                        下载 Excel
                    </Button>
                </Space>
            </Space>
        </Card>
    );
};

export default DataDownloadCard;
