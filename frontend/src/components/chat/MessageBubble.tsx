import React, { memo, useRef } from 'react';
import { Button, Card, Space, Tooltip, Typography, theme, Tag, Collapse } from 'antd';
import { 
    UserOutlined, RobotOutlined, CheckCircleOutlined, PartitionOutlined, 
    LikeOutlined, DislikeOutlined, PushpinOutlined, EditOutlined, 
    CodeOutlined, SearchOutlined, BulbOutlined, DownloadOutlined,
    BarChartOutlined, TableOutlined, ExpandOutlined, ShrinkOutlined,
    CopyOutlined, PlayCircleOutlined, QuestionCircleOutlined
} from '@ant-design/icons';
import ThinkingIndicator from './ThinkingIndicator';
import MarkdownRender from './MarkdownRender';
import TaskTimeline from '../TaskTimeline';
import ArtifactRenderer from '../ArtifactRenderer';
import MessageContentCard from './MessageContentCard';
import { MessageAnimation, ThinkingAnimation, TypingAnimation } from './MessageAnimations';
import AccessibilityWrapper, { useKeyboardNavigation, useScreenReaderNotification, useReducedMotion } from '../AccessibilityWrapper';
import { API_BASE_URL } from '../../config';
import type { Message, TaskItem } from '../../types';

interface MessageBubbleProps {
    item: Message;
    index: number;
    isDarkMode?: boolean;
    isLoading?: boolean;
    isLastMessage?: boolean;
    onSendMessage: (msg: string, cmd?: string, sql?: string, tables?: string[]) => void;
    setEditableSql: (sql: string) => void;
    setIsReviewOpen: (open: boolean) => void;
    setViewingPlan: (plan: TaskItem[]) => void;
    setIsPlanModalOpen: (open: boolean) => void;
    handleFeedback: (index: number, type: 'like' | 'dislike') => void;
    setEditablePythonCode: (code: string) => void;
    setPythonExecResult: (res: any) => void;
    setIsPythonEditOpen: (open: boolean) => void;
    latestData: any[];
}

const MessageBubble = memo(({ 
    item, index, isDarkMode, isLoading, isLastMessage, 
    onSendMessage, setEditableSql, setIsReviewOpen, 
    setViewingPlan, setIsPlanModalOpen, handleFeedback,
    setEditablePythonCode, setPythonExecResult, setIsPythonEditOpen,
    latestData 
}: MessageBubbleProps) => {
    const { token } = theme.useToken();
    const messageRef = useRef<HTMLDivElement>(null);
    const { notify } = useScreenReaderNotification();
    const prefersReducedMotion = useReducedMotion();

    // Setup keyboard navigation
    useKeyboardNavigation(messageRef as React.RefObject<HTMLElement>);

    // Helper to render content with new MessageContentCard
    const renderContent = (content: string | any, role: string) => {
        // Handle Code Generated Event
        if (role === 'agent' && typeof content === 'string' && item.isCode) {
            const code = content.replace(/```python\n|\n```/g, '');
            return (
                <MessageContentCard
                    type="code"
                    title="Python 分析代码"
                    icon={<CodeOutlined />}
                    actions={[
                        <Tooltip title="编辑并运行代码" key="edit">
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
                        </Tooltip>,
                        <Tooltip title="复制代码" key="copy">
                            <Button 
                                type="text" 
                                size="small" 
                                icon={<CopyOutlined />}
                                onClick={() => {
                                    navigator.clipboard.writeText(code);
                                    // 这里可以添加一个轻提示
                                }}
                            />
                        </Tooltip>
                    ]}
                    collapsible={true}
                    defaultExpanded={true}
                >
                    <div style={{ maxHeight: 300, overflow: 'auto' }}>
                        <pre style={{ 
                            margin: 0, 
                            fontSize: 13, 
                            fontFamily: 'var(--font-mono)', 
                            color: 'var(--text-secondary)',
                            lineHeight: 1.6,
                            padding: '8px 0'
                        }}>
                            {code}
                        </pre>
                    </div>
                </MessageContentCard>
            );
        }

        // Handle Plan Event
        if (role === 'agent' && item.plan) {
            return (
                <MessageContentCard
                    type="plan"
                    title="执行计划"
                    icon={<PartitionOutlined />}
                    actions={[
                        <Tooltip title="查看详细计划" key="view">
                            <Button 
                                type="link" 
                                size="small" 
                                icon={<ExpandOutlined />}
                                onClick={() => {
                                    if (item.plan) {
                                        setViewingPlan(item.plan);
                                        setIsPlanModalOpen(true);
                                    }
                                }}
                            >
                                查看详情
                            </Button>
                        </Tooltip>
                    ]}
                    collapsible={true}
                    defaultExpanded={false}
                >
                    <TaskTimeline tasks={item.plan} />
                </MessageContentCard>
            );
        }
        
        // Handle Clarification Event
        if (role === 'agent' && item.clarification) {
            return (
                <MessageContentCard
                    type="insight"
                    title="需要澄清意图"
                    icon={<QuestionCircleOutlined />}
                    actions={[]}
                    collapsible={false}
                    defaultExpanded={true}
                    style={{ 
                        borderColor: 'var(--primary-color)', 
                        background: isDarkMode ? 'rgba(22, 119, 255, 0.1)' : '#e6f4ff'
                    }}
                >
                    <div style={{ padding: '8px 0' }}>
                        <Typography.Text strong style={{ fontSize: 15, display: 'block', marginBottom: 12 }}>
                            {item.clarification.question}
                        </Typography.Text>
                        <Space wrap>
                            {item.clarification.options.map((option, idx) => (
                                <Button 
                                    key={idx}
                                    type="primary"
                                    ghost
                                    onClick={() => onSendMessage(option, "start", undefined, [option])}
                                    style={{ borderRadius: 16 }}
                                >
                                    {option}
                                </Button>
                            ))}
                        </Space>
                    </div>
                </MessageContentCard>
            );
        }

        // Handle Download Token
        if (role === 'agent' && item.downloadToken) {
            const url = `${API_BASE_URL}/query/download?token=${encodeURIComponent(item.downloadToken)}`;
            return (
                <MessageContentCard
                    type="download"
                    title="查询结果下载"
                    icon={<DownloadOutlined />}
                    actions={[
                        <Button 
                            type="primary" 
                            size="small"
                            icon={<DownloadOutlined />}
                            href={url} 
                            target="_blank"
                            key="download"
                        >
                            下载 CSV
                        </Button>
                    ]}
                >
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                        查询已完成，您可以下载结果数据进行进一步分析
                    </div>
                </MessageContentCard>
            );
        }

        // Handle Visualization
        if (role === 'agent' && item.vizOption) {
            return (
                <MessageContentCard
                    type="visualization"
                    title="数据可视化"
                    icon={<BarChartOutlined />}
                    actions={[
                        <Tooltip title="全屏查看" key="fullscreen">
                            <Button 
                                type="text" 
                                size="small" 
                                icon={<ExpandOutlined />}
                            />
                        </Tooltip>
                    ]}
                    collapsible={true}
                    defaultExpanded={true}
                >
                    <ArtifactRenderer 
                        code={`render(<ReactECharts option={data} style={{height: 400}} />);`}
                        data={item.vizOption}
                    />
                </MessageContentCard>
            );
        }

        // Handle Generative UI Component
        if (role === 'agent' && item.uiComponent) {
            return (
                <MessageContentCard
                    type="visualization"
                    title="动态组件"
                    icon={<TableOutlined />}
                    actions={[
                        <Tooltip title="展开查看" key="expand">
                            <Button 
                                type="text" 
                                size="small" 
                                icon={<ExpandOutlined />}
                            />
                        </Tooltip>
                    ]}
                    collapsible={true}
                    defaultExpanded={true}
                >
                    <ArtifactRenderer 
                        code={item.uiComponent}
                        data={item.data || latestData}
                        images={item.images}
                    />
                </MessageContentCard>
            );
        }

        if (typeof content === 'string') {
            return <MarkdownRender content={content} isDarkMode={isDarkMode} />;
        }
        
        return <div style={{minHeight: role === 'agent' ? 24 : 'auto', color: 'var(--text-primary)'}}>{content}</div>;
    };

    // Render Detective Insight with new MessageContentCard
    const renderInsights = () => {
        if (!item.hypotheses && !item.insights) return null;
        
        const isDetective = !!item.hypotheses;
        const data = item.hypotheses || item.insights || [];
        const title = isDetective ? 
            `侦探思考 (模式: ${item.analysisDepth === 'deep' ? '深度' : '快速'})` : 
            "主动洞察发现";
        const icon = isDetective ? <SearchOutlined /> : <BulbOutlined />;
        
        return (
            <MessageContentCard
                type="insight"
                title={title}
                icon={icon}
                collapsible={true}
                defaultExpanded={true}
            >
                <div style={{ paddingLeft: 8 }}>
                    {data.map((text, i) => (
                        <div 
                            key={i} 
                            className="insight-item"
                            style={{
                                color: 'var(--text-primary)',
                                marginBottom: i < data.length - 1 ? '8px' : '0',
                                padding: '4px 0',
                                borderLeft: '2px solid var(--warning-color)',
                                paddingLeft: '12px',
                                fontSize: 14,
                                lineHeight: 1.6,
                                '--item-index': i
                            } as React.CSSProperties}
                        >
                            {text}
                        </div>
                    ))}
                </div>
            </MessageContentCard>
        );
    };

    return (
        <MessageAnimation
            isUser={item.role === 'user'}
            isVisible={true}
            delay={index * 0.1}
        >
            <AccessibilityWrapper
                role="article"
                ariaLabel={`${item.role === 'user' ? '用户' : 'AI助手'}消息`}
                ref={messageRef}
                tabIndex={0}
            >
                <div style={{ 
                    display: 'flex', 
                    flexDirection: 'column',
                    alignItems: item.role === 'user' ? 'flex-end' : 'flex-start',
                    marginBottom: 24,
                    width: '100%',
                    animation: prefersReducedMotion ? 'none' : 'fadeIn 0.3s ease-in-out'
                }}>
            <div style={{ 
                display: 'flex', 
                flexDirection: item.role === 'user' ? 'row-reverse' : 'row',
                gap: 16,
                maxWidth: '92%',
                alignItems: 'flex-start'
            }}>
                {/* Avatar */}
                <div className={`avatar-container ${item.role === 'user' ? 'avatar-user' : 'avatar-agent'}`}
                     style={{ 
                         width: 40, 
                         height: 40, 
                         borderRadius: '12px', 
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
                        {/* Thinking Process with new animation */}
                        {item.role === 'agent' && item.thinking && (
                            <MessageContentCard
                                type="thinking"
                                title="正在思考..."
                                icon={<SearchOutlined />}
                                collapsible={true}
                                defaultExpanded={true}
                            >
                                <div style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                                    <ThinkingAnimation isVisible={isLoading && isLastMessage} />
                                    {item.thinking}
                                </div>
                            </MessageContentCard>
                        )}

                        {/* Detective / Insights */}
                        {renderInsights()}

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
                                            setEditableSql(item.content);
                                            setIsReviewOpen(true);
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

                        {/* Loading State - now handled by ThinkingAnimation */}
                        {!item.content && !item.thinking && item.role === 'agent' && !item.plan && !item.uiComponent && !item.vizOption && !item.downloadToken && (
                            <div style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                color: token.colorPrimary, 
                                gap: 12, 
                                padding: '8px 0' 
                            }}>
                                <div className="loading-dots-modern">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                                <span style={{ 
                                    fontSize: 14, 
                                    fontWeight: 500, 
                                    letterSpacing: '0.02em' 
                                }}>
                                    正在分析数据...
                                </span>
                            </div>
                        )}

                        {/* Loading State */}
                        {!item.content && !item.thinking && item.role === 'agent' && !item.plan && !item.uiComponent && !item.vizOption && !item.downloadToken && (
                                <div style={{ display: 'flex', alignItems: 'center', color: token.colorPrimary, gap: 12, padding: '8px 0' }}>
                                    <div className="loading-dots">
                                        <span></span>
                                        <span></span>
                                        <span></span>
                                    </div>
                                    <span style={{ fontSize: 14, fontWeight: 500, letterSpacing: '0.02em' }}>正在分析数据...</span>
                                </div>
                        )}
                        
                        <style>{`
                            .loading-dots {
                                display: flex;
                                gap: 4px;
                            }
                            .loading-dots span {
                                width: 6px;
                                height: 6px;
                                background-color: ${token.colorPrimary};
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

                    {/* Feedback & Actions Row */}
                    {item.role === 'agent' && (item.content || item.uiComponent) && (
                        <div className="message-actions" style={{ 
                            marginTop: 8, 
                            display: 'flex', 
                            gap: 8, 
                            opacity: 0.8,
                            paddingLeft: 4
                        }}>
                             <Space size="small">
                                {item.plan && (
                                    <Tooltip title="查看执行计划">
                                        <Button 
                                            className="message-feedback-btn"
                                            type="text" 
                                            size="small" 
                                            icon={<PartitionOutlined />} 
                                            style={{ 
                                                color: 'var(--text-tertiary)', 
                                                fontSize: 13
                                            }}
                                            onClick={() => {
                                                if (item.plan) {
                                                    setViewingPlan(item.plan);
                                                    setIsPlanModalOpen(true);
                                                }
                                            }}
                                            data-icon="partition"
                                        >
                                            计划
                                        </Button>
                                    </Tooltip>
                                )}
                                <Tooltip title="有帮助">
                                    <Button 
                                        className="message-feedback-btn"
                                        type="text" 
                                        size="small" 
                                        icon={<LikeOutlined />} 
                                        style={{ 
                                            color: 'var(--text-tertiary)', 
                                            fontSize: 13
                                        }}
                                        onClick={() => {
                                            handleFeedback(index, 'like');
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
                                            color: 'var(--text-tertiary)', 
                                            fontSize: 13
                                        }}
                                        onClick={() => {
                                            handleFeedback(index, 'dislike');
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
                        <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 8, paddingLeft: 4 }}>
                            <Tag 
                                icon={<BarChartOutlined />} 
                                style={{ 
                                    padding: '4px 12px', 
                                    borderRadius: 16, 
                                    cursor: 'pointer', 
                                    border: '1px solid var(--primary-color)', 
                                    color: 'var(--primary-color)', 
                                    background: 'var(--primary-bg)'
                                }}
                                onClick={() => onSendMessage("请帮我可视化上述数据", "start")}
                            >
                                可视化数据
                            </Tag>
                            <Tag 
                                icon={<TableOutlined />} 
                                style={{ 
                                    padding: '4px 12px', 
                                    borderRadius: 16, 
                                    cursor: 'pointer', 
                                    border: '1px solid var(--primary-color)', 
                                    color: 'var(--primary-color)', 
                                    background: 'var(--primary-bg)' 
                                }}
                                onClick={() => onSendMessage("请分析数据中的异常点", "start")}
                            >
                                分析异常
                            </Tag>
                             <Tag 
                                icon={<DownloadOutlined />} 
                                style={{ 
                                    padding: '4px 12px', 
                                    borderRadius: 16, 
                                    cursor: 'pointer', 
                                    border: '1px solid var(--primary-color)', 
                                    color: 'var(--primary-color)', 
                                    background: 'var(--primary-bg)' 
                                }}
                                onClick={() => onSendMessage("请生成详细的数据报告", "start")}
                            >
                                生成报告
                            </Tag>
                        </div>
                    )}
                </div>
            </div>
        </div>
            </AccessibilityWrapper>
        </MessageAnimation>
    );
}, (prev, next) => {
    if (prev.isDarkMode !== next.isDarkMode) return false;
    if (prev.item !== next.item) return false;
    if (prev.isLastMessage !== next.isLastMessage) return false;
    if (prev.isLastMessage && prev.isLoading !== next.isLoading) return false;
    return true; 
});

export default MessageBubble;
