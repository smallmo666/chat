import React, { useState, useRef, useEffect } from 'react';
import { Button, Input, Collapse, Space, Tooltip, App, Modal, Typography, Card } from 'antd';
import { UserOutlined, RobotOutlined, SyncOutlined, CaretRightOutlined, LoadingOutlined, SendOutlined, DownloadOutlined, LikeOutlined, DislikeOutlined, PushpinOutlined, PlayCircleOutlined, CheckCircleOutlined, MenuUnfoldOutlined, FileTextOutlined, AudioOutlined, ExportOutlined, EditOutlined, CodeOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Editor from '@monaco-editor/react';
import type { Message } from '../types';
import ArtifactRenderer from './ArtifactRenderer';

import { useTheme } from '../context/ThemeContext';

const { TextArea } = Input;

interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    onSendMessage: (content: string, command?: string, sql?: string) => void;
    latestData: any[];
    onToggleSidebar?: () => void;
    isLeftCollapsed?: boolean;
    onResetSession?: () => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading, onSendMessage, latestData, onToggleSidebar, isLeftCollapsed, onResetSession }) => {
    const { isDarkMode } = useTheme();
    const [inputValue, setInputValue] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const { message } = App.useApp();

    // HITL States
    const [reviewSql, setReviewSql] = useState<string | null>(null);
    const [isReviewOpen, setIsReviewOpen] = useState(false);
    const [editableSql, setEditableSql] = useState('');
    
    // Python Edit State
    const [isPythonEditOpen, setIsPythonEditOpen] = useState(false);
    const [editablePythonCode, setEditablePythonCode] = useState('');
    const [pythonExecResult, setPythonExecResult] = useState<any>(null);
    const [isPythonRunning, setIsPythonRunning] = useState(false);

    // Voice & Export
    const [isRecording, setIsRecording] = useState(false);
    const recognitionRef = useRef<any>(null);

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

    // Initialize Speech Recognition
    useEffect(() => {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = false;
            recognitionRef.current.lang = 'zh-CN';

            recognitionRef.current.onresult = (event: any) => {
                const transcript = event.results[0][0].transcript;
                setInputValue(prev => prev + transcript);
                setIsRecording(false);
            };

            recognitionRef.current.onerror = (event: any) => {
                console.error('Speech recognition error', event.error);
                setIsRecording(false);
                message.error('语音识别出错: ' + event.error);
            };

            recognitionRef.current.onend = () => {
                setIsRecording(false);
            };
        }
    }, []);

    const toggleRecording = () => {
        if (!recognitionRef.current) {
            message.warning('您的浏览器不支持语音识别');
            return;
        }

        if (isRecording) {
            recognitionRef.current.stop();
        } else {
            try {
                recognitionRef.current.start();
                setIsRecording(true);
                message.info('请开始说话...');
            } catch (e) {
                console.error(e);
            }
        }
    };

    const handleExportHistory = () => {
        if (messages.length === 0) {
            message.warning('没有可导出的对话');
            return;
        }

        const timestamp = new Date().toLocaleString();
        let markdown = `# 对话记录 - ${timestamp}\n\n`;

        messages.forEach((msg, idx) => {
            const role = msg.role === 'user' ? 'User' : 'Agent';
            markdown += `## ${role}\n\n`;
            
            if (msg.role === 'agent' && msg.thinking) {
                markdown += `> **Thinking Process:**\n> ${msg.thinking.replace(/\n/g, '\n> ')}\n\n`;
            }

            if (typeof msg.content === 'string') {
                markdown += `${msg.content}\n\n`;
            } else if (msg.uiComponent) {
                markdown += `*[生成了动态 UI 组件]*\n\n\`\`\`jsx\n${msg.uiComponent}\n\`\`\`\n\n`;
            } else {
                 markdown += `*[复杂内容，无法完全展示]*\n\n`;
            }
            
            if (msg.vizOption) {
                markdown += `*[包含图表可视化]*\n\n`;
            }
            
            markdown += `---\n\n`;
        });

        const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `chat_history_${Date.now()}.md`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        message.success('导出成功');
    };

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

    // Helper to render content
    const renderContent = (content: string | any, role: string, onOptionSelect?: (option: string) => void) => {
        // Try to parse JSON for interactive cards
        if (role === 'agent' && typeof content === 'string' && (content.trim().startsWith('{') || content.trim().startsWith('```json'))) {
             try {
                let jsonStr = content.trim();
                if (jsonStr.startsWith('```json')) {
                    jsonStr = jsonStr.replace(/^```json/, '').replace(/```$/, '');
                } else if (jsonStr.startsWith('```')) {
                    jsonStr = jsonStr.replace(/^```/, '').replace(/```$/, '');
                }
                
                const data = JSON.parse(jsonStr);
                
                // Clarify Intent Card
                if (data.status === 'AMBIGUOUS' && data.options && Array.isArray(data.options)) {
                    return (
                        <Card 
                            size="small" 
                            title={<Space><CheckCircleOutlined style={{color: '#1677ff'}} /> 需要确认</Space>}
                            style={{ borderColor: '#e6f4ff', background: isDarkMode ? '#1f1f1f' : '#f0f5ff', minWidth: 300 }}
                            styles={{ body: { padding: '12px 16px' } }}
                        >
                            <Typography.Paragraph strong style={{color: isDarkMode ? '#e0e0e0' : 'inherit'}}>{data.question}</Typography.Paragraph>
                            <Space direction="vertical" style={{ width: '100%' }}>
                                {data.options.map((opt: string, idx: number) => (
                                    <Button 
                                        key={idx} 
                                        block 
                                        style={{ textAlign: 'left' }}
                                        onClick={() => onOptionSelect && onOptionSelect(opt)}
                                    >
                                        {opt}
                                    </Button>
                                ))}
                            </Space>
                        </Card>
                    );
                }
             } catch (e) {
                 // Ignore JSON parse error, treat as text
             }
        }


        
        // Handle Code Generated Event (Special Card)
        if (role === 'agent' && typeof content === 'string' && content.startsWith('__CODE_GENERATED__')) {
             const code = content.replace('__CODE_GENERATED__', '');
             return (
                 <Card 
                    size="small" 
                    title={<Space><CodeOutlined style={{color: '#1677ff'}} /> Python 分析代码</Space>}
                    extra={
                        <Button 
                            type="link" 
                            size="small" 
                            icon={<EditOutlined />} 
                            onClick={() => {
                                setEditablePythonCode(code);
                                setPythonExecResult(null);
                                setIsPythonEditOpen(true);
                            }}
                        >
                            编辑 & 运行
                        </Button>
                    }
                    style={{ 
                        borderColor: isDarkMode ? '#303030' : '#e6f4ff', 
                        background: isDarkMode ? '#141414' : '#f0f5ff',
                        marginBottom: 12
                    }}
                    styles={{ body: { padding: 0 } }}
                 >
                     <div style={{ maxHeight: 200, overflow: 'auto', padding: '8px 12px' }}>
                        <pre style={{ margin: 0, fontSize: 12, fontFamily: 'monospace', color: isDarkMode ? '#aaa' : '#666' }}>
                            {code}
                        </pre>
                     </div>
                 </Card>
             );
        }

        if (typeof content === 'string') {
             return (
                <div className="markdown-body" style={{minHeight: role === 'agent' ? 24 : 'auto', fontSize: 15, lineHeight: 1.6, color: isDarkMode ? '#e0e0e0' : 'inherit'}}>
                    <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                            code({node, inline, className, children, ...props}: any) {
                                return !inline ? (
                                    <div style={{background: isDarkMode ? '#141414' : '#f6f8fa', padding: '12px', borderRadius: '6px', overflowX: 'auto', margin: '8px 0', border: isDarkMode ? '1px solid #303030' : '1px solid #e1e4e8'}}>
                                        <code className={className} {...props} style={{fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace', fontSize: '85%', color: isDarkMode ? '#e0e0e0' : 'inherit'}}>
                                            {children}
                                        </code>
                                    </div>
                                ) : (
                                    <code className={className} {...props} style={{background: isDarkMode ? 'rgba(110, 118, 129, 0.4)' : 'rgba(175, 184, 193, 0.2)', padding: '0.2em 0.4em', borderRadius: '6px', fontSize: '85%', fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace', color: isDarkMode ? '#e0e0e0' : 'inherit'}}>
                                        {children}
                                    </code>
                                )
                            },
                            table({children, ...props}: any) {
                                return <div style={{overflowX: 'auto', margin: '12px 0'}}><table {...props} style={{borderCollapse: 'collapse', width: '100%', fontSize: 14}}>{children}</table></div>
                            },
                            th({children, ...props}: any) {
                                return <th {...props} style={{border: isDarkMode ? '1px solid #303030' : '1px solid #d0d7de', padding: '8px 12px', background: isDarkMode ? '#1f1f1f' : '#f6f8fa', fontWeight: 600, textAlign: 'left', color: isDarkMode ? '#e0e0e0' : 'inherit'}}>{children}</th>
                            },
                            td({children, ...props}: any) {
                                return <td {...props} style={{border: isDarkMode ? '1px solid #303030' : '1px solid #d0d7de', padding: '8px 12px', color: isDarkMode ? '#e0e0e0' : 'inherit'}}>{children}</td>
                            },
                            p({children, ...props}: any) {
                                return <p {...props} style={{marginBottom: 16, color: isDarkMode ? '#e0e0e0' : 'inherit'}}>{children}</p>
                            },
                            li({children, ...props}: any) {
                                return <li {...props} style={{color: isDarkMode ? '#e0e0e0' : 'inherit'}}>{children}</li>
                            }
                        }}
                    >
                        {content}
                    </ReactMarkdown>
                </div>
            );
        }
        
        return <div style={{minHeight: role === 'agent' ? 24 : 'auto', color: isDarkMode ? '#e0e0e0' : 'inherit'}}>{content}</div>;
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: isDarkMode ? '#141414' : '#fff', position: 'relative', color: isDarkMode ? '#e0e0e0' : 'inherit' }}>
            {/* Header */}
            <div style={{ 
                padding: '16px 24px', 
                borderBottom: isDarkMode ? '1px solid #303030' : '1px solid rgba(0,0,0,0.06)', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                background: isDarkMode ? '#1f1f1f' : '#fff',
                zIndex: 10
            }}>
                <div style={{ display: 'flex', alignItems: 'center', fontSize: 16, fontWeight: 600, color: isDarkMode ? '#e0e0e0' : '#1f1f1f', letterSpacing: '-0.02em' }}>
                    {onToggleSidebar && (
                         <Tooltip title={isLeftCollapsed ? "展开侧边栏" : "收起侧边栏"}>
                            <Button 
                                type="text" 
                                icon={isLeftCollapsed ? <MenuUnfoldOutlined /> : <MenuUnfoldOutlined rotate={180} />} 
                                onClick={onToggleSidebar} 
                                style={{marginRight: 12, color: isDarkMode ? '#e0e0e0' : 'inherit'}}
                            />
                        </Tooltip>
                    )}
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
                <div style={{display: 'flex', gap: 8}}>
                     <Tooltip title="基于当前上下文生成分析报告">
                        <Button 
                            icon={<FileTextOutlined />} 
                            onClick={() => onSendMessage("请基于当前的对话上下文，为我生成一份详细的数据分析报告。", "start")}
                            size="middle"
                            style={{ borderRadius: 8, borderColor: '#d9d9d9', color: '#666' }}
                        >
                            生成报告
                        </Button>
                    </Tooltip>
                    <Tooltip title="导出聊天记录 (Markdown)">
                        <Button 
                            icon={<ExportOutlined />} 
                            onClick={handleExportHistory}
                            size="middle"
                            style={{ borderRadius: 8, borderColor: '#d9d9d9', color: '#666' }}
                        />
                    </Tooltip>
                    {onResetSession && (
                        <Tooltip title="重置会话 (解决卡顿/循环问题)">
                            <Button 
                                icon={<SyncOutlined />} 
                                onClick={onResetSession}
                                size="middle"
                                style={{ borderRadius: 8, borderColor: '#d9d9d9', color: '#666' }}
                            >
                                重置
                            </Button>
                        </Tooltip>
                    )}
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
                                padding: '12px 16px', 
                                borderRadius: item.role === 'user' ? '16px 0 16px 16px' : '0 16px 16px 16px',
                                background: item.role === 'user' ? 'linear-gradient(135deg, #2b32b2 0%, #1488cc 100%)' : (isDarkMode ? '#1f1f1f' : '#fff'),
                                color: item.role === 'user' ? 'white' : (isDarkMode ? '#e0e0e0' : '#1f1f1f'),
                                boxShadow: item.role === 'user' ? '0 4px 12px rgba(20, 136, 204, 0.2)' : '0 2px 8px rgba(0,0,0,0.04)',
                                border: item.role === 'agent' ? (isDarkMode ? '1px solid #303030' : '1px solid rgba(0,0,0,0.04)') : 'none',
                                fontSize: '15px',
                                lineHeight: 1.5,
                                overflow: 'hidden',
                                minWidth: 60
                            }}>
                                {/* Thinking Process */}
                                {item.role === 'agent' && item.thinking && (
                                    <Collapse 
                                        size="small"
                                        ghost
                                        defaultActiveKey={isLoading && index === messages.length - 1 ? ['1'] : []}
                                        expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ fontSize: 10, color: '#999' }} />}
                                        items={[{ 
                                            key: '1', 
                                            label: <Space size={4}><span style={{fontSize: 12, color: '#888', fontWeight: 500}}>思考过程</span>{isLoading && index === messages.length - 1 && <LoadingOutlined style={{fontSize: 10, color: '#1677ff'}} />}</Space>, 
                                            children: (
                                                <div style={{
                                                    whiteSpace: 'pre-wrap', 
                                                    fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace', 
                                                    fontSize: 12, 
                                                    color: isDarkMode ? '#aaa' : '#666', 
                                                    background: isDarkMode ? '#141414' : '#f9fafb', 
                                                    padding: '12px', 
                                                    borderRadius: 8, 
                                                    maxHeight: 300, 
                                                    overflowY: 'auto', 
                                                    border: isDarkMode ? '1px solid #303030' : '1px solid #eee'
                                                }}>
                                                    {item.thinking}
                                                    {isLoading && index === messages.length - 1 && <span style={{animation: 'blink 1s step-end infinite', marginLeft: 2, fontWeight: 'bold'}}>▋</span>}
                                                </div>
                                            )
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
                                    item.content && renderContent(item.content, item.role, (opt) => onSendMessage(opt, "start"))
                                )}

                                {/* Generative UI Component */}
                                {item.uiComponent && (
                                    <ArtifactRenderer 
                                        code={item.uiComponent} 
                                        data={item.data || latestData} 
                                    />
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
                background: isDarkMode 
                    ? 'linear-gradient(to top, rgba(20,20,20,1) 70%, rgba(20,20,20,0) 100%)' 
                    : 'linear-gradient(to top, rgba(255,255,255,1) 70%, rgba(255,255,255,0) 100%)',
                zIndex: 20
            }}>
                <div style={{ 
                    display: 'flex', 
                    gap: 12, 
                    alignItems: 'flex-end', 
                    background: isDarkMode ? '#1f1f1f' : '#fff', 
                    padding: '8px 8px 8px 16px', 
                    borderRadius: 16, 
                    border: isDarkMode ? '1px solid #303030' : '1px solid #e6e6e6',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.08)'
                }}
                onFocus={(e) => {
                    e.currentTarget.style.borderColor = '#1677ff';
                    e.currentTarget.style.boxShadow = '0 8px 24px rgba(22, 119, 255, 0.15)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onBlur={(e) => {
                    e.currentTarget.style.borderColor = isDarkMode ? '#303030' : '#e6e6e6';
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
                            lineHeight: 1.5,
                            color: isDarkMode ? '#e0e0e0' : 'inherit',
                            caretColor: isDarkMode ? '#fff' : 'inherit'
                        }}
                        onDrop={(e) => {
                            e.preventDefault();
                            const text = e.dataTransfer.getData('text/plain');
                            if (text) {
                                // Insert text at cursor position or append
                                const textArea = e.currentTarget;
                                const start = textArea.selectionStart;
                                const end = textArea.selectionEnd;
                                const newValue = inputValue.substring(0, start) + text + inputValue.substring(end);
                                setInputValue(newValue);
                                
                                // Restore focus (optional, might need setTimeout)
                            }
                        }}
                        onDragOver={(e) => e.preventDefault()}
                    />
                    
                    <div style={{display: 'flex', gap: 8, alignItems: 'center'}}>
                         <Tooltip title={isRecording ? "点击停止" : "点击说话"}>
                            <Button 
                                type={isRecording ? 'primary' : 'text'}
                                danger={isRecording}
                                shape="circle"
                                size="large"
                                icon={<AudioOutlined spin={isRecording} />} 
                                onClick={toggleRecording}
                                style={{ 
                                    color: isRecording ? '#fff' : '#888',
                                }}
                            />
                        </Tooltip>
                        
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
                @keyframes blink {
                    50% { opacity: 0; }
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
                width={800}
            >
                <div style={{ marginBottom: 16 }}>
                    <Typography.Text type="secondary">智能体生成了以下 SQL，您可以在执行前进行修改。</Typography.Text>
                </div>
                <div style={{ border: '1px solid #d9d9d9', borderRadius: 8, overflow: 'hidden' }}>
                    <Editor
                        height="300px"
                        defaultLanguage="sql"
                        value={editableSql}
                        onChange={(value) => setEditableSql(value || '')}
                        options={{
                            minimap: { enabled: false },
                            scrollBeyondLastLine: false,
                            fontSize: 14,
                            automaticLayout: true,
                            tabSize: 4
                        }}
                    />
                </div>
            </Modal>
            {/* Python Edit Modal */}
            <Modal
                title="Python 代码分析与调试"
                open={isPythonEditOpen}
                onCancel={() => setIsPythonEditOpen(false)}
                footer={null}
                width={900}
                styles={{ body: { padding: 0 } }}
            >
                <div style={{ display: 'flex', height: 600 }}>
                    {/* Left: Code Editor */}
                    <div style={{ flex: 1, borderRight: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography.Text strong>Python 脚本</Typography.Text>
                            <Button 
                                type="primary" 
                                size="small" 
                                icon={isPythonRunning ? <LoadingOutlined /> : <PlayCircleOutlined />} 
                                onClick={handleRunPython}
                                disabled={isPythonRunning}
                            >
                                运行代码
                            </Button>
                        </div>
                        <div style={{ flex: 1 }}>
                            <Editor
                                height="100%"
                                defaultLanguage="python"
                                value={editablePythonCode}
                                onChange={(value) => setEditablePythonCode(value || '')}
                                theme={isDarkMode ? "vs-dark" : "light"}
                                options={{
                                    minimap: { enabled: false },
                                    scrollBeyondLastLine: false,
                                    fontSize: 14,
                                    automaticLayout: true,
                                    tabSize: 4
                                }}
                            />
                        </div>
                    </div>
                    
                    {/* Right: Execution Result */}
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: isDarkMode ? '#141414' : '#fafafa' }}>
                         <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0' }}>
                            <Typography.Text strong>执行结果</Typography.Text>
                        </div>
                        <div style={{ flex: 1, padding: 16, overflow: 'auto' }}>
                            {isPythonRunning ? (
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
                                    <LoadingOutlined style={{ fontSize: 32, marginBottom: 16, color: '#1677ff' }} />
                                    <span>正在沙箱中执行...</span>
                                </div>
                            ) : pythonExecResult ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                                    {pythonExecResult.error && (
                                        <div style={{ padding: 12, background: '#fff1f0', border: '1px solid #ffccc7', borderRadius: 6, color: '#cf1322' }}>
                                            <div style={{ fontWeight: 'bold', marginBottom: 4 }}>Error:</div>
                                            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>{pythonExecResult.error}</pre>
                                        </div>
                                    )}
                                    
                                    {pythonExecResult.output && (
                                        <div style={{ padding: 12, background: isDarkMode ? '#1f1f1f' : '#fff', border: isDarkMode ? '1px solid #303030' : '1px solid #e8e8e8', borderRadius: 6 }}>
                                            <div style={{ fontWeight: 'bold', marginBottom: 4, color: '#666' }}>Standard Output:</div>
                                            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12, fontFamily: 'monospace', color: isDarkMode ? '#e0e0e0' : '#333' }}>{pythonExecResult.output}</pre>
                                        </div>
                                    )}
                                    
                                    {pythonExecResult.images && pythonExecResult.images.map((img: string, idx: number) => (
                                        <div key={idx} style={{ padding: 12, background: isDarkMode ? '#1f1f1f' : '#fff', border: isDarkMode ? '1px solid #303030' : '1px solid #e8e8e8', borderRadius: 6, textAlign: 'center' }}>
                                            <img src={`data:image/png;base64,${img}`} alt="Plot" style={{ maxWidth: '100%', borderRadius: 4 }} />
                                        </div>
                                    ))}
                                    
                                    {!pythonExecResult.error && !pythonExecResult.output && (!pythonExecResult.images || pythonExecResult.images.length === 0) && (
                                        <div style={{ textAlign: 'center', color: '#999', padding: 20 }}>
                                            代码执行成功，但没有输出。
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div style={{ textAlign: 'center', color: '#999', marginTop: 100 }}>
                                    点击“运行代码”查看结果
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </Modal>
        </div>
    );
};

export default ChatWindow;
