import { memo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import copy from 'copy-to-clipboard';
import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { Button, Tooltip, theme } from 'antd';

interface MarkdownRenderProps {
    content: string;
    isDarkMode?: boolean;
}

const CodeBlock = ({ inline, className, children, isDarkMode, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    const [copied, setCopied] = useState(false);
    const { token } = theme.useToken();

    const handleCopy = () => {
        copy(String(children).replace(/\n$/, ''));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (inline) {
        return (
            <code className={className} {...props} style={{
                background: isDarkMode ? 'rgba(110, 118, 129, 0.4)' : 'rgba(0,0,0,0.06)', 
                padding: '0.2em 0.4em', 
                borderRadius: '4px', 
                fontSize: '85%', 
                fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace', 
                color: isDarkMode ? '#e0e0e0' : token.colorPrimary,
                border: '1px solid rgba(0,0,0,0.05)'
            }}>
                {children}
            </code>
        );
    }

    return (
        <div style={{
            position: 'relative',
            margin: '16px 0',
            borderRadius: 8,
            overflow: 'hidden',
            border: `1px solid ${isDarkMode ? '#303030' : '#e0e0e0'}`,
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
        }}>
            {/* Header for language and copy button */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 12px',
                background: isDarkMode ? '#1f1f1f' : '#f5f5f5',
                borderBottom: `1px solid ${isDarkMode ? '#303030' : '#e0e0e0'}`,
                fontFamily: 'sans-serif',
                fontSize: 12,
                color: isDarkMode ? '#888' : '#666'
            }}>
                <span style={{ fontWeight: 600 }}>{language || 'text'}</span>
                <Tooltip title={copied ? "已复制" : "复制代码"}>
                    <Button 
                        type="text" 
                        size="small" 
                        icon={copied ? <CheckOutlined style={{ color: '#52c41a' }} /> : <CopyOutlined />} 
                        onClick={handleCopy}
                        style={{ 
                            height: 24, 
                            padding: '0 8px',
                            color: copied ? '#52c41a' : 'inherit'
                        }}
                    />
                </Tooltip>
            </div>
            
            <SyntaxHighlighter
                style={isDarkMode ? vscDarkPlus : vs}
                language={language}
                PreTag="div"
                customStyle={{
                    margin: 0,
                    padding: '16px',
                    fontSize: 13,
                    lineHeight: 1.5,
                    background: isDarkMode ? '#141414' : '#ffffff',
                }}
                {...props}
            >
                {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
        </div>
    );
};

const MarkdownRender = memo(({ content, isDarkMode = false }: MarkdownRenderProps) => (
    <div className="markdown-body" style={{fontSize: 15, lineHeight: 1.7, color: 'var(--text-primary)'}}>
        <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
                code: (props) => <CodeBlock {...props} isDarkMode={isDarkMode} />,
                table({children, ...props}: any) {
                    return (
                        <div style={{
                            overflowX: 'auto', 
                            margin: '16px 0', 
                            borderRadius: 8, 
                            border: '1px solid var(--border-color)',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
                        }}>
                            <table {...props} style={{
                                borderCollapse: 'collapse', 
                                width: '100%', 
                                fontSize: 14,
                                background: 'var(--bg-container)'
                            }}>
                                {children}
                            </table>
                        </div>
                    )
                },
                th({children, ...props}: any) {
                    return <th {...props} style={{
                        borderBottom: '1px solid var(--border-color)', 
                        padding: '12px 16px', 
                        background: isDarkMode ? 'rgba(255,255,255,0.04)' : '#fafafa', 
                        fontWeight: 600, 
                        textAlign: 'left', 
                        color: 'var(--text-secondary)',
                        fontSize: 13
                    }}>{children}</th>
                },
                td({children, ...props}: any) {
                    return <td {...props} style={{
                        borderBottom: '1px solid var(--border-color-split)', 
                        padding: '12px 16px', 
                        color: 'var(--text-primary)'
                    }}>{children}</td>
                },
                p({children, ...props}: any) {
                    return <div {...props} style={{marginBottom: 16}}>{children}</div>
                },
                li({children, ...props}: any) {
                    return <li {...props} style={{marginBottom: 6, paddingLeft: 4}}>{children}</li>
                },
                ul({children, ...props}: any) {
                    return <ul {...props} style={{paddingLeft: 24, marginBottom: 16}}>{children}</ul>
                },
                ol({children, ...props}: any) {
                    return <ol {...props} style={{paddingLeft: 24, marginBottom: 16}}>{children}</ol>
                },
                a({children, ...props}: any) {
                    return <a {...props} style={{
                        color: 'var(--primary-color)', 
                        textDecoration: 'none', 
                        fontWeight: 500,
                        borderBottom: '1px dashed transparent',
                        transition: 'all 0.2s'
                    }} className="hover-underline" target="_blank" rel="noopener noreferrer">{children}</a>
                },
                blockquote({children, ...props}: any) {
                    return <blockquote {...props} style={{
                        borderLeft: '4px solid var(--primary-color)',
                        margin: '16px 0',
                        padding: '8px 16px',
                        background: 'var(--primary-bg)',
                        color: 'var(--text-secondary)',
                        borderRadius: '0 8px 8px 0'
                    }}>{children}</blockquote>
                }
            }}
        >
            {content}
        </ReactMarkdown>
        <style>{`
            .hover-underline:hover {
                border-bottom-color: var(--primary-color) !important;
            }
        `}</style>
    </div>
), (prev, next) => prev.content === next.content && prev.isDarkMode === next.isDarkMode);

export default MarkdownRender;
