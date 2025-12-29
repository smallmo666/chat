import React, { useState, useRef, useEffect } from 'react';
import { Card, Button, Input, Collapse, Table, Tag } from 'antd';
import { UserOutlined, RobotOutlined, SyncOutlined, CaretRightOutlined, LoadingOutlined, SendOutlined, DownloadOutlined, FileTextOutlined, TableOutlined, BarChartOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import type { Message } from '../types';

const { TextArea } = Input;

interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    onSendMessage: (content: string) => void;
    latestData: any[];
}

const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading, onSendMessage, latestData }) => {
    const [inputValue, setInputValue] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = () => {
        if (!inputValue.trim()) return;
        onSendMessage(inputValue);
        setInputValue('');
    };

    const handleDownload = (data: any[]) => {
        if (!data || data.length === 0) return;
        
        // Convert to CSV
        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(fieldName => {
                const val = row[fieldName];
                return JSON.stringify(val === null || val === undefined ? '' : val);
            }).join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `query_result_${Date.now()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Chat Area */}
            <div style={{ flex: 1, padding: '16px 16px 0 16px', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <Card 
                    title={<span style={{display: 'flex', alignItems: 'center'}}><UserOutlined style={{marginRight: 8}}/> 对话交互</span>}
                    variant="borderless"
                    extra={
                        latestData.length > 0 && (
                            <Button 
                                icon={<DownloadOutlined />} 
                                onClick={() => handleDownload(latestData)}
                            >
                                导出最新结果
                            </Button>
                        )
                    }
                    style={{ height: '100%', display: 'flex', flexDirection: 'column', boxShadow: 'none', background: '#fafafa' }}
                    styles={{ body: { flex: 1, overflowY: 'auto', padding: '16px', background: 'white', borderRadius: '0 0 8px 8px' } }}
                >
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {messages.map((item, index) => (
                        <div key={index} style={{ padding: '8px 0' }}>
                            <div style={{ 
                                width: '100%', 
                                display: 'flex', 
                                justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start' 
                            }}>
                                <div style={{ 
                                    maxWidth: item.role === 'user' ? '80%' : '100%', 
                                    padding: '10px 14px', 
                                    borderRadius: item.role === 'user' ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                                    background: item.role === 'user' ? '#1677ff' : '#f5f5f5',
                                    color: item.role === 'user' ? 'white' : 'rgba(0,0,0,0.88)',
                                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                                    fontSize: '14px',
                                    lineHeight: 1.6,
                                    overflow: 'hidden' // Ensure content like charts doesn't overflow bubble
                                }}>
                                    {item.role === 'agent' && (
                                        <div style={{display: 'flex', alignItems: 'center', marginBottom: 4, opacity: 0.7, fontSize: 12}}>
                                        <RobotOutlined style={{ marginRight: 4 }} /> Agent
                                        </div>
                                    )}
                                    
                                    {/* Thinking Process */}
                                    {item.role === 'agent' && item.thinking && (
                                        <Collapse 
                                            size="small"
                                            ghost
                                            expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ fontSize: 10, color: '#888' }} />}
                                            items={[{ 
                                                key: '1', 
                                                label: <span style={{fontSize: 12, color: '#888'}}>思考过程</span>, 
                                                children: <div style={{whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, color: '#666', background: '#eee', padding: 8, borderRadius: 4, maxHeight: 300, overflowY: 'auto'}}>{item.thinking}</div>
                                            }]}
                                            style={{ marginBottom: 8, background: 'rgba(0,0,0,0.02)', borderRadius: 4 }}
                                        />
                                    )}

                                    {/* Result Content */}
                                    {item.content && <div style={{whiteSpace: 'pre-wrap'}}>{item.content}</div>}
                                    
                                    {/* Loading State for empty content */}
                                    {!item.content && !item.thinking && item.role === 'agent' && (
                                            <SyncOutlined spin style={{color: '#1677ff'}} />
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                    </div>
                    <div ref={messagesEndRef} />
                </Card>
            </div>

            {/* Input Area (Fixed at bottom) */}
            <div style={{ padding: '0 16px 16px 16px', flexShrink: 0 }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', background: 'white', padding: 12, borderRadius: 12, border: '1px solid #f0f0f0' }}>
                <TextArea 
                    value={inputValue}
                    onChange={e => setInputValue(e.target.value)}
                    onPressEnter={(e) => {
                        if (!e.shiftKey) {
                            e.preventDefault();
                            handleSend();
                        }
                    }}
                    placeholder="请输入您的查询，例如：查询所有年龄大于20的用户..." 
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    style={{ borderRadius: 8, padding: '8px 12px', resize: 'none', border: 'none', boxShadow: 'none', background: '#f9f9f9' }}
                />
                <Button 
                    type="primary" 
                    size="large"
                    icon={isLoading ? <LoadingOutlined /> : <SendOutlined />} 
                    onClick={handleSend}
                    disabled={isLoading}
                    style={{ height: 'auto', padding: '0 20px', borderRadius: 8 }}
                >
                    发送
                </Button>
            </div>
            </div>
        </div>
    );
};

export default ChatWindow;
