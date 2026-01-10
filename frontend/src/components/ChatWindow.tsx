import React, { useState, useRef, useEffect } from 'react';
import { Button, Tooltip, Modal, Typography, theme } from 'antd';
import { 
    MenuUnfoldOutlined, MenuFoldOutlined, FileTextOutlined, 
    ExportOutlined, SyncOutlined, DownloadOutlined, PlayCircleOutlined,
    LoadingOutlined, ArrowDownOutlined
} from '@ant-design/icons';
import { useTheme } from '../context/ThemeContext';
import type { Message, TaskItem } from '../chatTypes';
import MessageBubble from './chat/MessageBubble';
import InputBar from './chat/InputBar';
import WelcomeScreen from './chat/WelcomeScreen';
import TaskTimeline from './TaskTimeline';
import UserGuidance, { useUserGuidance } from './UserGuidance';
import AccessibilityWrapper, { useScreenReaderNotification } from './AccessibilityWrapper';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { message as antdMessage } from 'antd';

const MonacoEditor = React.lazy(() => import('@monaco-editor/react'));

interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    onSendMessage: (content: string, command?: string, sql?: string, tables?: string[]) => void;
    latestData: any[];
    onToggleSidebar?: () => void;
    isLeftCollapsed?: boolean;
    onResetSession?: () => void;
    projectId?: string;
    projectName?: string;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ 
    messages, isLoading, onSendMessage, latestData, 
    onToggleSidebar, isLeftCollapsed, onResetSession, 
    projectId, projectName 
}) => {
    const { isDarkMode } = useTheme();
    const { token } = theme.useToken();
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const [showScrollButton, setShowScrollButton] = useState(false);
    const userScrolledUpRef = useRef(false);
    const { needsGuidance } = useUserGuidance();
    const { notify } = useScreenReaderNotification();

    // Modal States
    const [viewingPlan, setViewingPlan] = useState<TaskItem[] | null>(null);
    const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);
    const [isReviewOpen, setIsReviewOpen] = useState(false);
    const [editableSql, setEditableSql] = useState('');
    const [isPythonEditOpen, setIsPythonEditOpen] = useState(false);
    const [editablePythonCode, setEditablePythonCode] = useState('');
    const [pythonExecResult, setPythonExecResult] = useState<any>(null);
    const [isPythonRunning, setIsPythonRunning] = useState(false);

    const scrollToBottom = (smooth = true) => {
        messagesEndRef.current?.scrollIntoView({ behavior: smooth ? "smooth" : "auto" });
        userScrolledUpRef.current = false;
        setShowScrollButton(false);
    };

    const handleScroll = () => {
        if (!scrollContainerRef.current) return;
        const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
        const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
        
        userScrolledUpRef.current = !isNearBottom;
        setShowScrollButton(!isNearBottom);
    };

    useEffect(() => {
        // Only auto-scroll if user hasn't scrolled up, or if it's a new user message (which usually implies sending)
        const lastMsg = messages[messages.length - 1];
        const isUserMsg = lastMsg?.role === 'user';

        if (!userScrolledUpRef.current || isUserMsg) {
            scrollToBottom();
        }
    }, [messages]);

    // Watch for interrupt messages
    useEffect(() => {
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === 'agent' && lastMsg.interrupt) {
            setEditableSql(lastMsg.content);
            setIsReviewOpen(true);
        }
    }, [messages]);

    const handleExportHistory = () => {
        if (messages.length === 0) {
            antdMessage.warning('没有可导出的对话');
            notify('没有可导出的对话');
            return;
        }

        const timestamp = new Date().toLocaleString();
        let markdown = `# 对话记录 - ${timestamp}\n\n`;

        messages.forEach((msg) => {
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
        antdMessage.success('导出成功');
        notify('对话历史已导出成功');
    };

    const handleDownload = (data: any[]) => {
        if (!data || data.length === 0) return;
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

    const handleApprove = () => {
        onSendMessage("", "approve");
        setIsReviewOpen(false);
    };
  
    const handleEditAndRun = () => {
        onSendMessage("", "edit", editableSql);
        setIsReviewOpen(false);
    };

    const handleRunPython = async () => {
        if (!projectId) {
            antdMessage.error("未找到项目上下文");
            return;
        }
        setIsPythonRunning(true);
        setPythonExecResult(null);
        try {
            const token = localStorage.getItem('token');
            const response = await axios.post(`${API_BASE_URL}/chat/python/execute`, {
                code: editablePythonCode,
                project_id: projectId
            }, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            setPythonExecResult(response.data);
            antdMessage.success("代码执行完成");
        } catch (e: any) {
            console.error(e);
            setPythonExecResult({
                error: e.response?.data?.detail || e.message || "Execution failed"
            });
            antdMessage.error("代码执行出错");
        } finally {
            setIsPythonRunning(false);
        }
    };

    return (
        <AccessibilityWrapper
            role="main"
            ariaLabel="智能对话助手"
            className="chat-window-container"
            style={{ height: '100%' }}
        >
            <UserGuidance 
                isFirstTime={needsGuidance}
                onComplete={() => notify('引导完成，开始您的数据分析之旅！')}
            />
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', color: 'var(--text-primary)' }}>
            {/* Header */}
            <div className="glass-panel chat-header" style={{ 
                padding: '16px 24px', 
                borderBottom: '1px solid var(--border-color)', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                zIndex: 10,
                background: isDarkMode ? 'rgba(30,30,30,0.8)' : 'rgba(255,255,255,0.7)',
                borderTop: 'none',
                borderLeft: 'none',
                borderRight: 'none',
                borderRadius: 0
            }}>
                <div style={{ display: 'flex', alignItems: 'center', fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                    {onToggleSidebar && (
                         <Tooltip title={isLeftCollapsed ? "展开侧边栏" : "收起侧边栏"}>
                            <Button 
                                type="text" 
                                icon={isLeftCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} 
                                onClick={onToggleSidebar} 
                                style={{marginRight: 12, color: 'var(--text-primary)'}}
                            />
                        </Tooltip>
                    )}
                    {projectName || '智能对话助手'}
                </div>
                <div style={{display: 'flex', gap: 8}}>
                     <Tooltip title="基于当前上下文生成分析报告">
                        <Button 
                            icon={<FileTextOutlined />} 
                            onClick={() => onSendMessage("请基于当前的对话上下文，为我生成一份详细的数据分析报告。", "start")}
                            size="middle"
                            style={{ borderRadius: 8 }}
                        >
                            生成报告
                        </Button>
                    </Tooltip>
                    <Tooltip title="导出聊天记录 (Markdown)">
                        <Button 
                            icon={<ExportOutlined />} 
                            onClick={handleExportHistory}
                            size="middle"
                            style={{ borderRadius: 8 }}
                        />
                    </Tooltip>
                    {onResetSession && (
                        <Tooltip title="重置会话">
                            <Button 
                                icon={<SyncOutlined />} 
                                onClick={onResetSession}
                                size="middle"
                                style={{ borderRadius: 8 }}
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
                            style={{ borderRadius: 8 }}
                        >
                            导出结果
                        </Button>
                    )}
                </div>
            </div>

            {/* Chat Area */}
            <div 
                ref={scrollContainerRef}
                onScroll={handleScroll}
                style={{ 
                    flex: 1, 
                    overflowY: 'auto', 
                    padding: '20px 24px 120px 24px', 
                    scrollBehavior: 'smooth',
                    display: 'flex',
                    flexDirection: 'column'
                }} 
                className="chat-scroll-container message-container"
                role="log"
                aria-label="对话记录"
                aria-live="polite"
            >
                <div style={{ 
                    display: 'flex', 
                    flexDirection: 'column', 
                    gap: 0, 
                    maxWidth: 900, 
                    width: '100%',
                    margin: '0 auto',
                    flex: '1 0 auto',
                    justifyContent: 'flex-start'
                }}>
                {messages.length === 0 && (
                    <WelcomeScreen 
                        onSampleClick={(q) => onSendMessage(q, "start")} 
                        isDarkMode={isDarkMode}
                        projectName={projectName}
                    />
                )}
                {messages.map((item, index) => (
                    <MessageBubble 
                        key={index}
                        item={item}
                        isDarkMode={isDarkMode}
                        isLoading={isLoading}
                        isLastMessage={index === messages.length - 1}
                        onSendMessage={onSendMessage}
                        setEditableSql={setEditableSql}
                        setIsReviewOpen={setIsReviewOpen}
                        setViewingPlan={setViewingPlan}
                        setIsPlanModalOpen={setIsPlanModalOpen}
                        setEditablePythonCode={setEditablePythonCode}
                        setPythonExecResult={setPythonExecResult}
                        setIsPythonEditOpen={setIsPythonEditOpen}
                        latestData={latestData}
                    />
                ))}
                </div>
                <div ref={messagesEndRef} />
            </div>

            {/* Scroll to bottom button */}
            {showScrollButton && (
                <div style={{
                    position: 'absolute',
                    bottom: 120,
                    right: 40,
                    zIndex: 15,
                    animation: 'fadeIn 0.2s'
                }}>
                    <Button 
                        shape="circle" 
                        size="large"
                        icon={<ArrowDownOutlined />} 
                        onClick={() => scrollToBottom(true)}
                        style={{
                            boxShadow: 'var(--shadow-md)',
                            border: '1px solid var(--border-color)',
                            color: token.colorPrimary
                        }}
                    />
                    {isLoading && (
                        <div style={{
                            position: 'absolute',
                            top: -8,
                            right: -4,
                            width: 12,
                            height: 12,
                            background: '#ff4d4f',
                            borderRadius: '50%',
                            border: '2px solid white'
                        }} />
                    )}
                </div>
            )}

            {/* Input Bar */}
            <div className="chat-input-area">
                <InputBar 
                    onSend={(msg) => onSendMessage(msg, isLoading ? "interrupt" : "start")} 
                    isLoading={isLoading} 
                    isReviewOpen={isReviewOpen}
                    isDarkMode={isDarkMode}
                />
            </div>

            {/* Modals - Using global styles */}
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
                className="glass-modal"
            >
                <div style={{ marginBottom: 16 }}>
                    <Typography.Text type="secondary">智能体生成了以下 SQL，您可以在执行前进行修改。</Typography.Text>
                </div>
                <div style={{ border: '1px solid var(--border-color)', borderRadius: 8, overflow: 'hidden' }}>
                    <React.Suspense fallback={<div style={{height:300, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-tertiary)'}}><LoadingOutlined style={{marginRight:8}} />加载编辑器...</div>}>
                    <MonacoEditor
                        height="300px"
                        defaultLanguage="sql"
                        value={editableSql}
                        onChange={(value) => setEditableSql(value || '')}
                        options={{ minimap: { enabled: false }, fontSize: 14 }}
                        theme={isDarkMode ? "vs-dark" : "light"}
                    />
                    </React.Suspense>
                </div>
            </Modal>

            <Modal
                title="Python 代码分析与调试"
                open={isPythonEditOpen}
                onCancel={() => setIsPythonEditOpen(false)}
                footer={null}
                width={900}
                styles={{ body: { padding: 0 } }}
                className="glass-modal"
            >
                 <div style={{ display: 'flex', height: 600 }}>
                    <div style={{ flex: 1, borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography.Text strong>Python 脚本</Typography.Text>
                            <Button type="primary" size="small" icon={isPythonRunning ? <LoadingOutlined /> : <PlayCircleOutlined />} onClick={handleRunPython} disabled={isPythonRunning}>运行代码</Button>
                        </div>
                        <div style={{ flex: 1 }}>
                            <React.Suspense fallback={<div>Loading...</div>}>
                            <MonacoEditor height="100%" defaultLanguage="python" value={editablePythonCode} onChange={(value) => setEditablePythonCode(value || '')} theme={isDarkMode ? "vs-dark" : "light"} />
                            </React.Suspense>
                        </div>
                    </div>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: isDarkMode ? '#141414' : '#fafafa' }}>
                         <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border-color)' }}><Typography.Text strong>执行结果</Typography.Text></div>
                        <div style={{ flex: 1, padding: 16, overflow: 'auto' }}>
                            {pythonExecResult && (
                                <pre style={{whiteSpace: 'pre-wrap', fontSize: 12, fontFamily: 'var(--font-mono)'}}>{JSON.stringify(pythonExecResult, null, 2)}</pre>
                            )}
                        </div>
                    </div>
                </div>
            </Modal>

            <Modal
                title="执行计划详情"
                open={isPlanModalOpen}
                onCancel={() => setIsPlanModalOpen(false)}
                footer={null}
                width={600}
                className="glass-modal"
            >
                <div style={{ maxHeight: '60vh', overflowY: 'auto', padding: '12px 0' }}>
                    {viewingPlan ? <TaskTimeline tasks={viewingPlan} /> : <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: 20 }}>无执行计划数据</div>}
                </div>
            </Modal>

            <style>{`
                .chat-scroll-container::-webkit-scrollbar {
                    width: 6px;
                }
                .chat-scroll-container::-webkit-scrollbar-thumb {
                    background-color: transparent;
                }
                .chat-scroll-container:hover::-webkit-scrollbar-thumb {
                    background-color: rgba(0,0,0,0.1);
                }
            `}</style>
        </div>
        </AccessibilityWrapper>
    );
};

export default ChatWindow;
