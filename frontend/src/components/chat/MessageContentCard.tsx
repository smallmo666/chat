import React from 'react';
import { Card, Space, Button, Tooltip } from 'antd';
import { 
    CodeOutlined, SearchOutlined, BulbOutlined, 
    BarChartOutlined, TableOutlined, DownloadOutlined,
    EditOutlined, ExpandOutlined, ShrinkOutlined
} from '@ant-design/icons';
import { useState } from 'react';

interface MessageContentCardProps {
    type: 'code' | 'insight' | 'visualization' | 'download' | 'plan' | 'thinking';
    title: string;
    icon?: React.ReactNode;
    children: React.ReactNode;
    actions?: React.ReactNode[];
    collapsible?: boolean;
    defaultExpanded?: boolean;
    className?: string;
    style?: React.CSSProperties;
}

const MessageContentCard: React.FC<MessageContentCardProps> = ({
    type,
    title,
    icon,
    children,
    actions,
    collapsible = false,
    defaultExpanded = true,
    className = '',
    style
}) => {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    const getTypeIcon = () => {
        if (icon) return icon;
        switch (type) {
            case 'code': return <CodeOutlined />;
            case 'insight': return <BulbOutlined />;
            case 'visualization': return <BarChartOutlined />;
            case 'download': return <DownloadOutlined />;
            case 'plan': return <SearchOutlined />;
            case 'thinking': return <SearchOutlined />;
            default: return null;
        }
    };

    const getCardStyles = () => {
        const baseStyles = {
            marginTop: 8,
            marginBottom: 8,
            borderRadius: 12,
            transition: 'all 0.3s ease',
            overflow: 'hidden'
        };

        const typeStyles = {
            code: {
                background: 'var(--bg-container)',
                border: '1px solid var(--border-color)',
                boxShadow: 'var(--shadow-sm)'
            },
            insight: {
                background: 'linear-gradient(135deg, #fff7e6 0%, #fffbe6 100%)',
                border: '1px solid #ffe58f',
                boxShadow: '0 2px 8px rgba(255, 229, 143, 0.3)'
            },
            visualization: {
                background: 'var(--bg-container)',
                border: '1px solid var(--primary-color)',
                boxShadow: '0 2px 8px rgba(22, 119, 255, 0.15)'
            },
            download: {
                background: 'var(--bg-container)',
                border: '1px solid var(--success-color)',
                boxShadow: '0 2px 8px rgba(82, 196, 26, 0.15)'
            },
            plan: {
                background: 'var(--bg-container)',
                border: '1px solid var(--primary-color)',
                boxShadow: 'var(--shadow-sm)'
            },
            thinking: {
                background: 'rgba(22, 119, 255, 0.05)',
                border: '1px dashed var(--primary-color)',
                animation: 'pulse 2s infinite'
            }
        };

        return {
            ...baseStyles,
            ...typeStyles[type],
            ...style
        };
    };

    const header = (
        <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            width: '100%'
        }}>
            <Space>
                <span style={{ color: 'var(--primary-color)' }}>
                    {getTypeIcon()}
                </span>
                <span style={{ 
                    fontWeight: 500, 
                    fontSize: 14,
                    color: type === 'insight' ? '#d48806' : 'var(--text-primary)'
                }}>
                    {title}
                </span>
            </Space>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {actions && <div>{actions}</div>}
                {collapsible && (
                    <Tooltip title={isExpanded ? '收起' : '展开'}>
                        <Button
                            type="text"
                            size="small"
                            icon={isExpanded ? <ShrinkOutlined /> : <ExpandOutlined />}
                            onClick={() => setIsExpanded(!isExpanded)}
                            style={{ color: 'var(--text-tertiary)' }}
                        />
                    </Tooltip>
                )}
            </div>
        </div>
    );

    return (
        <Card
            size="small"
            title={header}
            className={`message-content-card ${className}`}
            style={getCardStyles()}
            styles={{
                header: {
                    padding: '8px 12px',
                    borderBottom: isExpanded ? '1px solid var(--border-color)' : 'none',
                    minHeight: 40
                },
                body: {
                    padding: isExpanded ? '12px 16px' : '0',
                    display: isExpanded ? 'block' : 'none'
                }
            }}
        >
            {isExpanded && children}
        </Card>
    );
};

export default MessageContentCard;