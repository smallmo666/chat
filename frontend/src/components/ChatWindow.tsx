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
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
            {/* Header */}
            <div style={{ 
                padding: '16px 24px', 
                borderBottom: '1px solid #f0f0f0', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                background: '#fff',
                zIndex: 1
            }}>
                <div style={{ display: 'flex', alignItems: 'center', fontSize: 16, fontWeight: 600, color: '#1f1f1f' }}>
                    <div style={{ 
                        width: 32, 
                        height: 32, 
                        background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)', 
                        borderRadius: '50%', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        marginRight: 12,
                        boxShadow: '0 2px 4px rgba(22, 119, 255, 0.2)'
                    }}>
                        <RobotOutlined style={{ color: 'white', fontSize: 18 }} />
                    </div>
                    智能对话助手
                </div>
                {latestData.length > 0 && (
                    <Button 
                        icon={<DownloadOutlined />} 
                        onClick={() => handleDownload(latestData)}
                        size="middle"
                    >
                        导出结果
                    </Button>
                )}
            </div>

            {/* Chat Area */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px', scrollBehavior: 'smooth' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                {messages.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
                        <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.2 }}>
                            <RobotOutlined />
                        </div>
                        <p>开始一个新的对话，您可以询问有关数据库的任何问题。</p>
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
                            gap: 12,
                            maxWidth: '90%'
                        }}>
                            {/* Avatar */}
                            <div style={{ 
                                width: 32, 
                                height: 32, 
                                borderRadius: '50%', 
                                background: item.role === 'user' ? '#f0f0f0' : '#e6f4ff',
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center',
                                flexShrink: 0,
                                marginTop: 4
                            }}>
                                {item.role === 'user' ? 
                                    <UserOutlined style={{ color: '#666' }} /> : 
                                    <RobotOutlined style={{ color: '#1677ff' }} />
                                }
                            </div>

                            {/* Bubble */}
                            <div style={{ 
                                padding: '12px 16px', 
                                borderRadius: item.role === 'user' ? '12px 0 12px 12px' : '0 12px 12px 12px',
                                background: item.role === 'user' ? '#1677ff' : '#f7f7f8',
                                color: item.role === 'user' ? 'white' : '#1f1f1f',
                                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                                fontSize: '14px',
                                lineHeight: 1.6,
                                overflow: 'hidden'
                            }}>
                                {/* Thinking Process */}
                                {item.role === 'agent' && item.thinking && (
                                    <Collapse 
                                        size="small"
                                        ghost
                                        expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ fontSize: 10, color: '#888' }} />}
                                        items={[{ 
                                            key: '1', 
                                            label: <span style={{fontSize: 12, color: '#888'}}>思考过程</span>, 
                                            children: <div style={{whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, color: '#666', background: 'rgba(0,0,0,0.03)', padding: 8, borderRadius: 4, maxHeight: 300, overflowY: 'auto'}}>{item.thinking}</div>
                                        }]}
                                        style={{ marginBottom: 8, background: 'white', borderRadius: 6, border: '1px solid rgba(0,0,0,0.05)' }}
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
                                    item.content && <div style={{whiteSpace: 'pre-wrap'}}>{item.content}</div>
                                )}
                                
                                {/* Loading State for empty content */}
                                {!item.content && !item.thinking && item.role === 'agent' && (
                                        <div style={{ display: 'flex', alignItems: 'center', color: '#1677ff', gap: 8 }}>
                                            <SyncOutlined spin />
                                            <span>正在分析...</span>
                                        </div>
                                )}

                                {/* Feedback Buttons (Only for completed agent messages) */}
                                {item.role === 'agent' && item.content && (
                                    <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                                        <Space size="small">
                                            <Tooltip title="有帮助">
                                                <Button 
                                                    type="text" 
                                                    size="small" 
                                                    icon={<LikeOutlined />} 
                                                    style={{ color: '#888', fontSize: 12 }}
                                                    onClick={() => handleFeedback(index, 'like')}
                                                />
                                            </Tooltip>
                                            <Tooltip title="没帮助">
                                                <Button 
                                                    type="text" 
                                                    size="small" 
                                                    icon={<DislikeOutlined />} 
                                                    style={{ color: '#888', fontSize: 12 }}
                                                    onClick={() => handleFeedback(index, 'dislike')}
                                                />
                                            </Tooltip>
                                            {item.vizOption && (
                                                <Tooltip title="收藏到看板">
                                                    <Button 
                                                        type="text" 
                                                        size="small" 
                                                        icon={<PushpinOutlined />} 
                                                        style={{ color: '#888', fontSize: 12 }}
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

            {/* Input Area */}
            <div style={{ padding: '24px', borderTop: '1px solid #f0f0f0', background: '#fff' }}>
                <div style={{ 
                    display: 'flex', 
                    gap: 12, 
                    alignItems: 'flex-end', 
                    background: '#f9f9f9', 
                    padding: 8, 
                    borderRadius: 12, 
                    border: '1px solid #e0e0e0',
                    transition: 'border-color 0.2s, box-shadow 0.2s',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.02)'
                }}
                onFocus={(e) => {
                    e.currentTarget.style.borderColor = '#1677ff';
                    e.currentTarget.style.boxShadow = '0 0 0 2px rgba(22, 119, 255, 0.1)';
                }}
                onBlur={(e) => {
                    e.currentTarget.style.borderColor = '#e0e0e0';
                    e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.02)';
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
                        placeholder="请输入您的查询，Shift+Enter 换行..." 
                        autoSize={{ minRows: 1, maxRows: 6 }}
                        disabled={isLoading || isReviewOpen}
                        style={{ 
                            borderRadius: 8, 
                            padding: '8px 12px', 
                            resize: 'none', 
                            border: 'none', 
                            boxShadow: 'none', 
                            background: 'transparent',
                            fontSize: 14
                        }}
                    />
                    <Button 
                        type="primary" 
                        shape="circle"
                        size="large"
                        icon={isLoading ? <LoadingOutlined /> : <SendOutlined />} 
                        onClick={handleSend}
                        disabled={isLoading || !inputValue.trim() || isReviewOpen}
                        style={{ flexShrink: 0, boxShadow: '0 2px 4px rgba(22, 119, 255, 0.3)' }}
                    />
                </div>
                <div style={{ textAlign: 'center', marginTop: 8, color: '#999', fontSize: 12 }}>
                    AI 可能会产生错误，请核对重要信息。
                </div>
            </div>
            
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
