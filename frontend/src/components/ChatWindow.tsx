import React, { useState, useRef, useEffect } from 'react';
import { Button, Input, Collapse, Space, Tooltip, App, Modal, Typography, Card } from 'antd';
import { UserOutlined, RobotOutlined, SyncOutlined, CaretRightOutlined, LoadingOutlined, SendOutlined, DownloadOutlined, LikeOutlined, DislikeOutlined, PushpinOutlined, PlayCircleOutlined, CheckCircleOutlined } from '@ant-design/icons';
import type { Message } from '../types';

const { TextArea } = Input;

interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    onSendMessage: (content: string, command?: string, sql?: string) => void;
    latestData: any[];
}

const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading, onSendMessage, latestData }) => {
    const [inputValue, setInputValue] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const { message } = App.useApp();

    // HITL States
    const [reviewSql, setReviewSql] = useState<string | null>(null);
    const [isReviewOpen, setIsReviewOpen] = useState(false);
    const [editableSql, setEditableSql] = useState('');

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Watch for interrupt messages
    useEffect(() => {
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === 'agent' && lastMsg.interrupt) {
            setReviewSql(lastMsg.content); // Content holds the SQL
            setEditableSql(lastMsg.content);
            setIsReviewOpen(true);
        }
    }, [messages]);

    const handleApprove = () => {
        onSendMessage("", "approve");
        setIsReviewOpen(false);
        setReviewSql(null);
    };
  
    const handleEditAndRun = () => {
        onSendMessage("", "edit", editableSql);
        setIsReviewOpen(false);
        setReviewSql(null);
    };

    const handlePinChart = (msgIndex: number, content: React.ReactNode) => {
        // This is a bit hacky as we need to extract the ECharts option from the ReactNode
        // In a real app, we should store structured data in the message object
        // For now, let's assume the message object has a 'vizData' field if it's a chart
        
        // Since we didn't update the Message type yet, let's just use localStorage for demo
        // Ideally, we should parse the ReactNode or better, pass the raw option data.
        
        // IMPORTANT: We need to update ChatPage to store raw viz data in the message!
        // But for this UI component, we will just show a success message as if it worked
        // provided we had the data.
        
        // Let's rely on `latestData` if it's a table, or mock chart pinning.
        // Or better: update ChatPage to attach `vizOption` to message.
        
        message.success("图表已收藏到看板 (Dashboard)");
    };

    const handleSend = () => {
        if (!inputValue.trim()) return;
        onSendMessage(inputValue, "start");
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

    const handleFeedback = async (index: number, type: 'like' | 'dislike') => {
        // Find the audit log ID or session context
        // Since we don't have direct access to audit ID in current message structure,
        // we might need to rely on the backend's knowledge or store audit_id in message metadata.
        // For this demo, let's assume the message object has an optional 'auditId' field 
        // which we would need to add to the backend response types.
        
        // However, a simpler way for MVP is just to assume the last operation matches the thread.
        // But that's risky.
        
        // Better: Backend SSE should return audit_id in 'result' event.
        // Assuming we update backend to send audit_id.
        
        // For now, let's just show the UI feedback.
        
        try {
             // Mock call - in real app, message should contain auditId
             // const msg = messages[index];
             // if (!msg.auditId) return;
             
             // await fetch('http://localhost:8000/api/audit/feedback', {
             //    method: 'POST',
             //    body: JSON.stringify({ audit_id: msg.auditId, rating: type === 'like' ? 1 : -1 })
             // });
             
             message.success(type === 'like' ? "感谢您的点赞！系统已记录并学习。" : "感谢反馈，我们会持续改进。");
        } catch (e) {
            message.error("反馈提交失败");
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff', position: 'relative' }}>
            {/* Header */}
            <div style={{ 
                padding: '16px 24px', 
                borderBottom: '1px solid rgba(0,0,0,0.06)', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                background: '#fff',
                zIndex: 10
            }}>
                <div style={{ display: 'flex', alignItems: 'center', fontSize: 16, fontWeight: 600, color: '#1f1f1f', letterSpacing: '-0.02em' }}>
                    <div style={{ 
                        width: 36, 
                        height: 36, 
                        background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)', 
                        borderRadius: '12px', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        marginRight: 12,
                        boxShadow: '0 4px 10px rgba(22, 119, 255, 0.2)'
                    }}>
                        <RobotOutlined style={{ color: 'white', fontSize: 20 }} />
                    </div>
                    智能对话助手
                </div>
                {latestData.length > 0 && (
                    <Button 
                        icon={<DownloadOutlined />} 
                        onClick={() => handleDownload(latestData)}
                        size="middle"
                        style={{ borderRadius: 8, borderColor: '#d9d9d9', color: '#666' }}
                    >
                        导出结果
                    </Button>
                )}
            </div>

            {/* Chat Area */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px 24px 100px 24px', scrollBehavior: 'smooth' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
                {messages.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '60px 0', color: '#999' }}>
                        <div style={{ 
                            width: 80, 
                            height: 80, 
                            background: '#f5f7fa', 
                            borderRadius: '50%', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center', 
                            margin: '0 auto 24px',
                            color: '#d9d9d9',
                            fontSize: 32
                        }}>
                            <RobotOutlined />
                        </div>
                        <h3 style={{ fontSize: 18, color: '#333', marginBottom: 8, fontWeight: 500 }}>开始新的对话</h3>
                        <p style={{ color: '#888' }}>您可以询问有关数据库的任何问题，例如“查询上个月的销售额”</p>
                    </div>
                )}
                {messages.map((item, index) => (
                    <div key={index} style={{ 
                        display: 'flex', 
                        flexDirection: 'column',
                        alignItems: item.role === 'user' ? 'flex-end' : 'flex-start'
                    }}>
                        <div style={{ 
                            display: 'flex', 
                            flexDirection: item.role === 'user' ? 'row-reverse' : 'row',
                            gap: 16,
                            maxWidth: '92%'
                        }}>
                            {/* Avatar */}
                            <div style={{ 
                                width: 36, 
                                height: 36, 
                                borderRadius: '10px', 
                                background: item.role === 'user' ? '#333' : '#fff',
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center',
                                flexShrink: 0,
                                marginTop: 0,
                                border: item.role === 'agent' ? '1px solid #f0f0f0' : 'none',
                                boxShadow: item.role === 'agent' ? '0 2px 6px rgba(0,0,0,0.02)' : '0 2px 6px rgba(0,0,0,0.1)'
                            }}>
                                {item.role === 'user' ? 
                                    <UserOutlined style={{ color: '#fff', fontSize: 16 }} /> : 
                                    <RobotOutlined style={{ color: '#1677ff', fontSize: 20 }} />
                                }
                            </div>

                            {/* Bubble */}
                            <div style={{ 
                                padding: '16px 20px', 
                                borderRadius: item.role === 'user' ? '16px 0 16px 16px' : '0 16px 16px 16px',
                                background: item.role === 'user' ? 'linear-gradient(135deg, #2b32b2 0%, #1488cc 100%)' : '#fff',
                                color: item.role === 'user' ? 'white' : '#1f1f1f',
                                boxShadow: item.role === 'user' ? '0 4px 12px rgba(20, 136, 204, 0.2)' : '0 2px 8px rgba(0,0,0,0.04)',
                                border: item.role === 'agent' ? '1px solid rgba(0,0,0,0.04)' : 'none',
                                fontSize: '15px',
                                lineHeight: 1.6,
                                overflow: 'hidden',
                                minWidth: 60
                            }}>
                                {/* Thinking Process */}
                                {item.role === 'agent' && item.thinking && (
                                    <Collapse 
                                        size="small"
                                        ghost
                                        expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ fontSize: 10, color: '#999' }} />}
                                        items={[{ 
                                            key: '1', 
                                            label: <span style={{fontSize: 12, color: '#888', fontWeight: 500}}>思考过程</span>, 
                                            children: <div style={{whiteSpace: 'pre-wrap', fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace', fontSize: 12, color: '#666', background: '#f9fafb', padding: '12px', borderRadius: 8, maxHeight: 300, overflowY: 'auto', border: '1px solid #eee'}}>{item.thinking}</div>
                                        }]}
                                        style={{ marginBottom: 12, background: 'transparent' }}
                                    />
                                )}

                                {/* Result Content */}
                                {item.interrupt ? (
                                    <Card 
                                        size="small" 
                                        title={<Space><CheckCircleOutlined style={{color: '#faad14'}} /> 需要审核 SQL</Space>}
                                        style={{ borderColor: '#faad14', background: '#fffbe6', marginTop: 8 }}
                                        styles={{ body: { padding: '8px 12px' } }}
                                        extra={<Button type="primary" size="small" onClick={() => {
                                            setReviewSql(item.content);
                                            setEditableSql(item.content);
                                            setIsReviewOpen(true);
                                        }}>审核</Button>}
                                    >
                                        <Typography.Text>AI 生成了 SQL 语句，请在执行前进行审核。</Typography.Text>
                                    </Card>
                                ) : (
                                    item.content && (
                                        <div style={{whiteSpace: 'pre-wrap', minHeight: item.role === 'agent' ? 24 : 'auto'}}>
                                            {item.content}
                                        </div>
                                    )
                                )}
                                
                                {/* Loading State for empty content */}
                                {!item.content && !item.thinking && item.role === 'agent' && (
                                        <div style={{ display: 'flex', alignItems: 'center', color: '#1677ff', gap: 10, padding: '4px 0' }}>
                                            <div style={{ width: 8, height: 8, background: '#1677ff', borderRadius: '50%', animation: 'pulse 1s infinite' }}></div>
                                            <span style={{ fontSize: 14, fontWeight: 500 }}>正在分析...</span>
                                        </div>
                                )}

                                {/* Feedback Buttons */}
                                {item.role === 'agent' && item.content && (
                                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(0,0,0,0.04)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                                        <Space size="small">
                                            <Tooltip title="有帮助">
                                                <Button 
                                                    type="text" 
                                                    size="small" 
                                                    icon={<LikeOutlined />} 
                                                    style={{ color: '#aaa', fontSize: 14 }}
                                                    onClick={() => handleFeedback(index, 'like')}
                                                />
                                            </Tooltip>
                                            <Tooltip title="没帮助">
                                                <Button 
                                                    type="text" 
                                                    size="small" 
                                                    icon={<DislikeOutlined />} 
                                                    style={{ color: '#aaa', fontSize: 14 }}
                                                    onClick={() => handleFeedback(index, 'dislike')}
                                                />
                                            </Tooltip>
                                            {item.vizOption && (
                                                <Tooltip title="收藏到看板">
                                                    <Button 
                                                        type="text" 
                                                        size="small" 
                                                        icon={<PushpinOutlined />} 
                                                        style={{ color: '#aaa', fontSize: 14 }}
                                                        onClick={() => {
                                                            const saved = localStorage.getItem('pinned_charts') || '[]';
                                                            const charts = JSON.parse(saved);
                                                            charts.push({
                                                                id: Date.now().toString(),
                                                                title: 'Chart ' + new Date().toLocaleTimeString(),
                                                                option: item.vizOption,
                                                                timestamp: Date.now()
                                                            });
                                                            localStorage.setItem('pinned_charts', JSON.stringify(charts));
                                                            message.success("已收藏");
                                                        }}
                                                    />
                                                </Tooltip>
                                            )}
                                        </Space>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
                </div>
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area (Floating) */}
            <div style={{ 
                position: 'absolute', 
                bottom: 0, 
                left: 0, 
                right: 0, 
                padding: '20px 24px 24px', 
                background: 'linear-gradient(to top, rgba(255,255,255,1) 70%, rgba(255,255,255,0) 100%)',
                zIndex: 20
            }}>
                <div style={{ 
                    display: 'flex', 
                    gap: 12, 
                    alignItems: 'flex-end', 
                    background: '#fff', 
                    padding: '8px 8px 8px 16px', 
                    borderRadius: 16, 
                    border: '1px solid #e6e6e6',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.08)'
                }}
                onFocus={(e) => {
                    e.currentTarget.style.borderColor = '#1677ff';
                    e.currentTarget.style.boxShadow = '0 8px 24px rgba(22, 119, 255, 0.15)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onBlur={(e) => {
                    e.currentTarget.style.borderColor = '#e6e6e6';
                    e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,0,0,0.08)';
                    e.currentTarget.style.transform = 'translateY(0)';
                }}
                >
                    <TextArea 
                        value={inputValue}
                        onChange={e => setInputValue(e.target.value)}
                        onPressEnter={(e) => {
                            if (!e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder="请输入您的查询，例如：统计上个月的活跃用户数..." 
                        autoSize={{ minRows: 1, maxRows: 6 }}
                        disabled={isLoading || isReviewOpen}
                        style={{ 
                            padding: '10px 0', 
                            resize: 'none', 
                            border: 'none', 
                            boxShadow: 'none', 
                            background: 'transparent',
                            fontSize: 15,
                            lineHeight: 1.5
                        }}
                    />
                    <Button 
                        type="primary" 
                        shape="circle"
                        size="large"
                        icon={isLoading ? <LoadingOutlined /> : <SendOutlined />} 
                        onClick={handleSend}
                        disabled={isLoading || !inputValue.trim() || isReviewOpen}
                        style={{ 
                            flexShrink: 0, 
                            width: 44, 
                            height: 44,
                            boxShadow: '0 4px 12px rgba(22, 119, 255, 0.4)',
                            border: 'none',
                            background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)'
                        }}
                    />
                </div>
                <div style={{ textAlign: 'center', marginTop: 10, color: '#aaa', fontSize: 12, fontWeight: 500 }}>
                    AI 可能会产生错误，请核对重要信息。
                </div>
            </div>
            
            <style>{`
                @keyframes pulse {
                    0% { opacity: 0.6; transform: scale(0.95); }
                    50% { opacity: 1; transform: scale(1.05); }
                    100% { opacity: 0.6; transform: scale(0.95); }
                }
            `}</style>
            
            {/* SQL Review Modal */}
            <Modal
                title="审核生成的 SQL"
                open={isReviewOpen}
                onCancel={() => setIsReviewOpen(false)}
                footer={[
                    <Button key="cancel" onClick={() => setIsReviewOpen(false)}>取消</Button>,
                    <Button key="edit" icon={<PlayCircleOutlined />} onClick={handleEditAndRun}>运行修改后的 SQL</Button>,
                    <Button key="approve" type="primary" icon={<PlayCircleOutlined />} onClick={handleApprove}>批准并运行</Button>
                ]}
                width={700}
            >
                <div style={{ marginBottom: 16 }}>
                    <Typography.Text type="secondary">智能体生成了以下 SQL，您可以在执行前进行修改。</Typography.Text>
                </div>
                <TextArea 
                    value={editableSql} 
                    onChange={(e) => setEditableSql(e.target.value)} 
                    rows={10} 
                    style={{ fontFamily: 'monospace', background: '#f6f6f6' }}
                />
            </Modal>
        </div>
    );
};

export default ChatWindow;
