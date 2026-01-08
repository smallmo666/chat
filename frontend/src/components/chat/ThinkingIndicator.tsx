import React, { useState, useEffect } from 'react';
import { Collapse, Space, theme } from 'antd';
import { CaretRightOutlined, SyncOutlined, BulbOutlined } from '@ant-design/icons';

interface ThinkingIndicatorProps {
    thinking: string;
    isLoading?: boolean;
    isDarkMode?: boolean;
}

const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({ thinking, isLoading, isDarkMode }) => {
    const { token } = theme.useToken();
    const [activeKey, setActiveKey] = useState<string[]>([]);

    // Auto-expand when loading starts, auto-collapse when loading finishes
    useEffect(() => {
        if (isLoading) {
            setActiveKey(['1']);
        } else {
            // Optional: Auto-collapse when done to save space
             setActiveKey([]); 
        }
    }, [isLoading]);

    if (!thinking) return null;

    return (
        <div style={{ marginBottom: 12, maxWidth: '100%', animation: 'fadeIn 0.5s ease' }}>
            <Collapse 
                size="small"
                ghost
                activeKey={activeKey}
                onChange={(keys) => setActiveKey(typeof keys === 'string' ? [keys] : keys)}
                expandIcon={({ isActive }) => (
                    <div style={{
                        background: isActive ? token.colorPrimaryBg : 'rgba(0,0,0,0.02)',
                        width: 20,
                        height: 20,
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                        marginTop: 2
                    }}>
                        <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ fontSize: 10, color: isActive ? token.colorPrimary : 'var(--text-tertiary)' }} />
                    </div>
                )}
                items={[{ 
                    key: '1', 
                    label: (
                        <Space size={8} style={{ display: 'flex', alignItems: 'center' }}>
                            <span style={{
                                fontSize: 13, 
                                color: 'var(--text-secondary)', 
                                fontWeight: 500,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8
                            }}>
                                {isLoading ? (
                                    <>
                                        <SyncOutlined spin style={{ color: token.colorPrimary, fontSize: 12 }} />
                                        <span className="thinking-text-gradient">AI 正在思考...</span>
                                    </>
                                ) : (
                                    <>
                                        <BulbOutlined style={{ color: 'var(--text-tertiary)', fontSize: 14 }} />
                                        <span>思考过程 ({thinking.length} 字符)</span>
                                    </>
                                )}
                            </span>
                        </Space>
                    ), 
                    children: (
                        <div style={{
                            position: 'relative',
                            marginTop: 4,
                            marginLeft: 4
                        }}>
                             {/* Connecting Line */}
                            <div style={{
                                position: 'absolute',
                                left: -14,
                                top: -12,
                                bottom: 10,
                                width: 2,
                                background: isDarkMode ? '#303030' : '#f0f0f0',
                                borderRadius: 2
                            }} />
                            
                            <div style={{
                                whiteSpace: 'pre-wrap', 
                                fontFamily: 'var(--font-mono)', 
                                fontSize: 12, 
                                color: 'var(--text-secondary)', 
                                background: isDarkMode ? 'rgba(255,255,255,0.02)' : '#f9fafb', 
                                padding: '12px 16px', 
                                borderRadius: 8, 
                                maxHeight: 300, 
                                overflowY: 'auto', 
                                border: '1px solid var(--border-color)',
                                lineHeight: 1.6
                            }}>
                                {thinking}
                                {isLoading && (
                                    <span className="typing-cursor" style={{ background: token.colorPrimary }}></span>
                                )}
                            </div>
                        </div>
                    )
                }]}
                style={{ background: 'transparent' }}
            />
            <style>{`
                @keyframes gradient-text {
                    0% { opacity: 0.6; }
                    50% { opacity: 1; }
                    100% { opacity: 0.6; }
                }
                .thinking-text-gradient {
                    background: linear-gradient(90deg, ${token.colorPrimary}, ${token.colorPrimaryActive});
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    animation: gradient-text 2s infinite;
                }
                .typing-cursor {
                    display: inline-block;
                    width: 6px;
                    height: 14px;
                    margin-left: 4px;
                    vertical-align: middle;
                    animation: blink 1s step-end infinite;
                    border-radius: 1px;
                }
                @keyframes blink {
                    50% { opacity: 0; }
                }
            `}</style>
        </div>
    );
};

export default ThinkingIndicator;
