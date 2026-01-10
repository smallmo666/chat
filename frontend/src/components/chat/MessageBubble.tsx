import React, { useState, memo } from 'react';
import { 
    UserOutlined, 
    RobotOutlined, 
    LikeOutlined, 
    DislikeOutlined, 
    BarChartOutlined, 
    TableOutlined, 
    SearchOutlined,
    CheckCircleOutlined,
    PlayCircleOutlined,
    DownloadOutlined
} from '@ant-design/icons';
import { Typography, Space, Button, Tooltip, Tag, theme, Checkbox, message, Table } from 'antd';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import MessageContentCard from './MessageContentCard';
import ThinkingAnimation from './ThinkingAnimation';
import VisualizationPanel from './VisualizationPanel';
import DataDownloadCard from './DataDownloadCard';
import MessageAnimation from './MessageAnimation';
import AccessibilityWrapper from '../common/AccessibilityWrapper';
import TaskTimeline from '../TaskTimeline';
import type { Message } from '../../chatTypes';

const { useToken } = theme;

interface MessageBubbleProps {
    item: Message;
    isLastMessage: boolean;
    isLoading: boolean;
    onSendMessage: (msg: string, command?: string, sql?: string, tables?: string[]) => void;
    isDarkMode?: boolean;
    // Parent State Setters
    setEditableSql?: (sql: string) => void;
    setIsReviewOpen?: (open: boolean) => void;
    setViewingPlan?: (plan: any) => void;
    setIsPlanModalOpen?: (open: boolean) => void;
    setEditablePythonCode?: (code: string) => void;
    setPythonExecResult?: (result: any) => void;
    setIsPythonEditOpen?: (open: boolean) => void;
    latestData?: any[];
}

// 提取 Loading 组件以复用
const LoadingIndicator = ({ color }: { color: string }) => (
    <div style={{ display: 'flex', alignItems: 'center', color: color, gap: 12, padding: '8px 0' }}>
        <div className="loading-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <span style={{ fontSize: 14, fontWeight: 500, letterSpacing: '0.02em' }}>正在分析数据...</span>
        <style>{`
            .loading-dots { display: flex; gap: 4px; }
            .loading-dots span {
                width: 6px; height: 6px;
                background-color: ${color};
                border-radius: 50%;
                animation: dots 1.4s infinite ease-in-out both;
            }
            .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
            .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
            @keyframes dots {
                0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
                40% { transform: scale(1); opacity: 1; }
            }
        `}</style>
    </div>
);

const MessageBubble: React.FC<MessageBubbleProps> = memo(({ 
    item, 
    isLastMessage, 
    isLoading, 
    onSendMessage,
    isDarkMode = false,
    setEditableSql,
    setIsReviewOpen
}) => {
    const { token } = useToken();
    // Removed local state that conflicts with parent props
    const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
    const [clarifySubmitted, setClarifySubmitted] = useState<boolean>(false);

    const [feedback, setFeedback] = useState<'like' | 'dislike' | null>(null);

    const handleFeedback = (type: 'like' | 'dislike') => {
        setFeedback(type);
        // Call actual API here if available
        console.log(`Feedback ${type} for session ${item.role}`);
    };

    const notify = (msg: string) => {
        message.success({
            content: msg,
            style: { marginTop: '10vh' }
        });
    };

    const renderContent = (content: string, role: string) => {
        return (
            <div className={`markdown-body ${role === 'user' ? 'user-message' : ''}`} style={{ 
                color: role === 'user' ? '#fff' : 'var(--text-primary)',
                fontSize: '15px'
            }}>
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                        code({node, inline, className, children, ...props}: any) {
                            const match = /language-(\w+)/.exec(className || '');
                            return !inline && match ? (
                                <SyntaxHighlighter
                                    style={vscDarkPlus}
                                    language={match[1]}
                                    PreTag="div"
                                    {...props}
                                >
                                    {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                            ) : (
                                <code className={className} {...props} style={{ 
                                    background: role === 'user' ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.06)',
                                    padding: '2px 6px',
                                    borderRadius: 4
                                }}>
                                    {children}
                                </code>
                            );
                        }
                    }}
                >
                    {content}
                </ReactMarkdown>
            </div>
        );
    };
    
    // Clarification Card Renderer
    const renderClarification = () => {
        if (!item.clarification) return null;
        
        const { question, options, type } = item.clarification;
        const safeOptions = Array.isArray(options) ? options : [];
        const isMultiple = type === 'multiple';
        
        return (
            <MessageContentCard
                type="clarification"
                title="需要您的确认"
                icon={<SearchOutlined />}
                defaultExpanded={true}
            >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <Typography.Text style={{ fontSize: 14 }}>{question}</Typography.Text>
                    
                    {safeOptions.length === 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                                暂无可选项，请直接在输入框补充你的选择，或点击跳过继续。
                            </Typography.Text>
                            <Button 
                                size="small"
                                onClick={() => {
                                    onSendMessage("", "clarify");
                                    setClarifySubmitted(true);
                                }}
                                style={{ width: 'fit-content' }}
                                disabled={clarifySubmitted}
                            >
                                跳过
                            </Button>
                        </div>
                    ) : isMultiple ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            <Checkbox.Group 
                                style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}
                                value={selectedOptions} 
                                onChange={(checkedValues) => setSelectedOptions(checkedValues as string[])}
                            >
                                {safeOptions.map((opt, idx) => (
                                    <Checkbox key={idx} value={opt} style={{ marginLeft: 0 }} disabled={clarifySubmitted}>
                                        {opt}
                                    </Checkbox>
                                ))}
                            </Checkbox.Group>
                            <Button 
                                type="primary" 
                                size="small"
                                disabled={clarifySubmitted || selectedOptions.length === 0}
                                onClick={() => {
                                    onSendMessage("", "clarify", undefined, selectedOptions);
                                    setSelectedOptions([]);
                                    setClarifySubmitted(true);
                                }}
                                style={{ width: 'fit-content' }}
                            >
                                确认选择
                            </Button>
                            <Button 
                                size="small"
                                onClick={() => {
                                    onSendMessage("", "clarify");
                                    setClarifySubmitted(true);
                                }}
                                style={{ width: 'fit-content' }}
                                disabled={clarifySubmitted}
                            >
                                跳过
                            </Button>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                            {safeOptions.map((opt, idx) => (
                                <Button 
                                    key={idx} 
                                    size="small"
                                    type="default"
                                    style={{ 
                                        borderRadius: 16, 
                                        fontSize: 13,
                                        borderColor: token.colorPrimary,
                                        color: token.colorPrimary
                                    }}
                                    onClick={() => {
                                        onSendMessage("", "clarify", undefined, [opt]);
                                        setClarifySubmitted(true);
                                    }}
                                    disabled={clarifySubmitted}
                                >
                                    {opt}
                                </Button>
                            ))}
                            <Button 
                                size="small"
                                type="default"
                                onClick={() => {
                                    onSendMessage("", "clarify");
                                    setClarifySubmitted(true);
                                }}
                                style={{ 
                                    borderRadius: 16, 
                                    fontSize: 13
                                }}
                                disabled={clarifySubmitted}
                            >
                                跳过
                            </Button>
                        </div>
                    )}
                </div>
            </MessageContentCard>
        );
    };

    const renderInsights = () => {
        if (!item.detectiveInsight) return null;
        return (
            <MessageContentCard
                type="insight"
                title="数据侦探分析"
                icon={<SearchOutlined />}
                defaultExpanded={true}
            >
                <ul style={{ paddingLeft: 20, margin: 0 }}>
                    {item.detectiveInsight.hypotheses.map((h: string, i: number) => (
                        <li key={i} style={{ marginBottom: 4 }}>{h}</li>
                    ))}
                </ul>
            </MessageContentCard>
        );
    };

    // 关键修复：判断是否为空白气泡
    // 如果没有 content，但有 thinking/substeps/clarification/plan 等，视为有效消息，不隐藏
    const hasAnyContent = item.content || item.thinking || item.clarification || item.plan || item.detectiveInsight || item.uiComponent || item.vizOption || item.downloadToken || (item.actionLogs && item.actionLogs.length > 0);

    return (
        <MessageAnimation>
            <AccessibilityWrapper role="article" ariaLabel={`${item.role} message`}>
        <div className={`message-bubble-container ${item.role}`} style={{ 
            display: 'flex', 
            justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: 24,
            width: '100%',
            padding: '0 20px',
            boxSizing: 'border-box'
        }}>
            <div style={{ 
                display: 'flex', 
                flexDirection: item.role === 'user' ? 'row-reverse' : 'row',
                alignItems: 'flex-start',
                maxWidth: '900px', 
                width: '100%',
                gap: 16
            }}>
                {/* Avatar */}
                 <div style={{ 
                         width: 40, height: 40, borderRadius: '12px', 
                         background: item.role === 'user' ? 'transparent' : 'var(--bg-container)',
                         display: 'flex', 
                         alignItems: 'center', 
                         justifyContent: 'center',
                         flexShrink: 0,
                         marginTop: 2,
                         border: item.role === 'agent' ? '1px solid var(--border-color)' : 'none',
                         boxShadow: item.role === 'agent' ? 'var(--shadow-sm)' : 'none'
                     }}>
                    {item.role === 'user' ? 
                        <div style={{
                            width: '100%', height: '100%', borderRadius: '12px',
                            background: `linear-gradient(135deg, var(--primary-color) 0%, var(--primary-active) 100%)`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            boxShadow: '0 4px 12px rgba(22, 119, 255, 0.3)'
                        }}>
                             <UserOutlined style={{ color: '#fff', fontSize: 18 }} /> 
                        </div>
                        : 
                        <RobotOutlined style={{ color: 'var(--primary-color)', fontSize: 22 }} />
                    }
                </div>

                {/* Bubble */}
                <div style={{ 
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: item.role === 'user' ? 'flex-end' : 'flex-start',
                    width: '100%'
                }}>
                    <div className={item.role === 'user' ? 'message-bubble-user' : 'message-bubble-agent'} style={{ 
                        padding: item.role === 'user' ? '12px 18px' : '18px 24px', 
                        fontSize: '15px',
                        lineHeight: 1.7,
                        overflow: 'hidden',
                        minWidth: 120,
                        maxWidth: '100%',
                        borderRadius: item.role === 'user' ? '18px 4px 18px 18px' : '4px 18px 18px 18px',
                        boxShadow: item.role === 'user' ? '0 4px 12px rgba(22, 119, 255, 0.2)' : '0 4px 12px rgba(0,0,0,0.03)',
                        border: item.role === 'user' ? 'none' : '1px solid var(--border-color)',
                        background: item.role === 'user' ? `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryActive} 100%)` : 'var(--bg-container)'
                    }}>
                        {/* Execution Process / Plan / Thinking */}
                        {item.role === 'agent' && (item.plan || item.thinking || (item.actionLogs && item.actionLogs.length > 0)) && (
                            <MessageContentCard
                                type="thinking"
                                title="执行过程"
                                icon={<SearchOutlined />}
                                collapsible={true}
                                defaultExpanded={true}
                            >
                                <div style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                                    {/* Task Timeline */}
                                    {item.plan && item.plan.length > 0 && (
                                        <div style={{ marginBottom: 16 }}>
                                            <TaskTimeline tasks={item.plan} />
                                        </div>
                                    )}

                                    {/* Thinking Text */}
                                    {item.thinking && (
                                        <div style={{ 
                                            padding: '8px 12px', 
                                            background: 'rgba(0,0,0,0.02)', 
                                            borderRadius: 8,
                                            borderLeft: '2px solid var(--primary-color)'
                                        }}>
                                            <div style={{ fontWeight: 500, marginBottom: 4, fontSize: 12, color: 'var(--text-tertiary)' }}>思维链</div>
                                            {item.thinking}
                                        </div>
                                    )}

                                    <ThinkingAnimation isVisible={isLoading && isLastMessage} text={item.currentTask} />
                                </div>
                            </MessageContentCard>
                        )}

                        {/* Clarification Request */}
                        {renderClarification()}

                        {/* Detective / Insights */}
                        {renderInsights()}
                        
                        {/* Visualization Options */}
                        {item.vizOption && !item.tableData && (
                            <VisualizationPanel 
                                config={item.vizOption} 
                                onUpdateConfig={(newConfig) => console.log(newConfig)} 
                            />
                        )}
                        {item.tableData && (
                            <MessageContentCard
                                type="insight"
                                title="可视化（表格）"
                                icon={<TableOutlined />}
                                defaultExpanded={true}
                            >
                                <div style={{ width: '100%', overflowX: 'auto' }}>
                                    <Table
                                        size="small"
                                        pagination={false}
                                        dataSource={(item.tableData.data || []).map((row: any, idx: number) => ({ key: idx, ...row }))}
                                        columns={(item.tableData.columns || []).map((k: string) => ({ title: k, dataIndex: k, key: k }))}
                                    />
                                </div>
                            </MessageContentCard>
                        )}
                        
                        {/* UI Component */}
                        {item.uiComponent && (
                            <div className="ui-component-wrapper" style={{ margin: '12px 0' }}>
                                <div dangerouslySetInnerHTML={{ __html: item.uiComponent }} />
                            </div>
                        )}

                        {/* Data Download */}
                        {item.downloadToken && (
                            <DataDownloadCard token={item.downloadToken} />
                        )}

                        {/* Data Preview (avoid duplicate when table visualization exists) */}
                        {item.data && Array.isArray(item.data) && item.data.length > 0 && !item.tableData && (
                            <MessageContentCard
                                type="insight"
                                title="结果预览"
                                icon={<TableOutlined />}
                                defaultExpanded={true}
                            >
                                <div style={{ width: '100%', overflowX: 'auto' }}>
                                    <Table
                                        size="small"
                                        pagination={false}
                                        dataSource={item.data.slice(0, 20).map((row: any, idx: number) => ({ key: idx, ...row }))}
                                        columns={Object.keys(item.data[0] || {}).map((k: string) => ({ title: k, dataIndex: k, key: k }))}
                                    />
                                </div>
                            </MessageContentCard>
                        )}

                        {/* Result Content */}
                        {item.interrupt ? (
                            <MessageContentCard
                                type="insight"
                                title="需要审核 SQL"
                                icon={<CheckCircleOutlined />}
                                actions={[
                                    <Button 
                                        type="primary" 
                                        size="small" 
                                        icon={<PlayCircleOutlined />}
                                        onClick={() => {
                                            if (setEditableSql) setEditableSql(item.content);
                                            if (setIsReviewOpen) setIsReviewOpen(true);
                                        }}
                                        key="review"
                                    >
                                        审核 SQL
                                    </Button>
                                ]}
                                style={{ 
                                    borderColor: 'var(--warning-color)', 
                                    background: isDarkMode ? 'rgba(255,190,0,0.05)' : '#fffbe6'
                                }}
                            >
                                <Typography.Text style={{ fontSize: 14 }}>
                                    AI 生成了 SQL 语句，请在执行前进行审核以确保安全性。
                                </Typography.Text>
                            </MessageContentCard>
                        ) : (
                            item.content && renderContent(item.content, item.role)
                        )}

                        {/* Loading State - Explicitly render if waiting for content but has structure */}
                        {isLoading && isLastMessage && !hasAnyContent && (
                            <LoadingIndicator color={token.colorPrimary} />
                        )}
                        
                        {/* Fallback for completely empty state (should not happen often now) */}
                        {!hasAnyContent && !isLoading && item.role === 'agent' && (
                           <div style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
                               (等待响应...)
                           </div>
                        )}
                    </div>

                    {/* Feedback & Actions Row */}
                    {item.role === 'agent' && hasAnyContent && (
                        <div className="message-actions" style={{ 
                            marginTop: 8, 
                            display: 'flex', 
                            gap: 8, 
                            opacity: 0.8,
                            paddingLeft: 4
                        }}>
                             <Space size="small">
                                <Tooltip title="有帮助">
                                    <Button 
                                        className="message-feedback-btn"
                                        type="text" 
                                        size="small" 
                                        icon={<LikeOutlined />} 
                                        style={{ 
                                            color: feedback === 'like' ? token.colorSuccess : 'var(--text-tertiary)', 
                                            fontSize: 13,
                                            background: feedback === 'like' ? 'rgba(82, 196, 26, 0.1)' : 'transparent'
                                        }}
                                        onClick={() => {
                                            handleFeedback('like');
                                            notify("感谢您的点赞！系统已记录并学习。");
                                        }}
                                        data-icon="like"
                                    />
                                </Tooltip>
                                <Tooltip title="没帮助">
                                    <Button 
                                        className="message-feedback-btn"
                                        type="text" 
                                        size="small" 
                                        icon={<DislikeOutlined />} 
                                        style={{ 
                                            color: feedback === 'dislike' ? token.colorError : 'var(--text-tertiary)', 
                                            fontSize: 13,
                                            background: feedback === 'dislike' ? 'rgba(255, 77, 79, 0.1)' : 'transparent'
                                        }}
                                        onClick={() => {
                                            handleFeedback('dislike');
                                            notify("感谢反馈，我们会持续改进。");
                                        }}
                                        data-icon="dislike"
                                    />
                                </Tooltip>
                            </Space>
                        </div>
                    )}

                    {/* Next Step Suggestions (Only for last agent message) */}
                    {isLastMessage && item.role === 'agent' && !isLoading && (
                        <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 10, paddingLeft: 4 }}>
                            <span style={{ fontSize: 12, color: token.colorTextTertiary, width: '100%', marginBottom: 4 }}>建议操作:</span>
                            {[
                                { label: '可视化分析', icon: <BarChartOutlined />, msg: '请帮我可视化上述数据', type: 'viz' },
                                { label: '异常检测', icon: <SearchOutlined />, msg: '请分析数据中的异常点', type: 'insight' },
                                { label: '生成报表', icon: <DownloadOutlined />, msg: '请生成详细的数据报告', type: 'report' }
                            ].map((suggest, idx) => (
                                <Tag 
                                    key={idx}
                                    icon={suggest.icon} 
                                    style={{ 
                                        padding: '6px 16px', 
                                        borderRadius: 20, 
                                        cursor: 'pointer', 
                                        border: `1px solid ${token.colorPrimary}`, 
                                        color: token.colorPrimary, 
                                        background: isDarkMode ? 'rgba(22, 119, 255, 0.1)' : '#fff',
                                        fontSize: 13,
                                        marginInlineEnd: 0,
                                        boxShadow: '0 2px 4px rgba(0,0,0,0.02)',
                                        transition: 'all 0.3s'
                                    }}
                                    className="suggestion-tag"
                                    onClick={() => onSendMessage(suggest.msg, "start")}
                                >
                                    {suggest.label}
                                </Tag>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
            </AccessibilityWrapper>
        </MessageAnimation>
    );
}, (prev, next) => {
    // 关键优化：Deep comparison for substeps updates
    if (prev.item.actionLogs?.length !== next.item.actionLogs?.length) return false;
    if (prev.item.plan?.length !== next.item.plan?.length) return false;
    // Check subtasks length change in plan
    if (prev.item.plan && next.item.plan) {
        if (prev.item.plan.some((t, i) => t.subtasks?.length !== next.item.plan![i].subtasks?.length)) return false;
    }
    if (prev.item.thinking !== next.item.thinking) return false;
    
    if (prev.isDarkMode !== next.isDarkMode) return false;
    if (prev.item !== next.item) return false;
    if (prev.isLastMessage !== next.isLastMessage) return false;
    if (prev.isLastMessage && prev.isLoading !== next.isLoading) return false;
    return true; 
});

export default MessageBubble;
