import React, { useEffect, useRef, useState, Suspense } from 'react';
import * as antd from 'antd';
import * as icons from '@ant-design/icons';
import { Button, Tooltip, Modal, theme, Space, Typography } from 'antd';
import { 
    FullscreenOutlined, 
    FullscreenExitOutlined, 
    WarningOutlined,
    BarChartOutlined} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import * as Babel from '@babel/standalone';

interface ArtifactRendererProps {
    code: string;
    data: any;
    images?: string[];
}

const ArtifactRenderer: React.FC<ArtifactRendererProps> = ({ code, data, images }) => {
    const { token } = theme.useToken();
    const containerRef = useRef<HTMLDivElement>(null);
    const [error, setError] = useState<string | null>(null);
    const [Component, setComponent] = useState<React.ReactNode | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);

    useEffect(() => {
        if (!code) return;

        try {
            // 1. Remove Imports (new Function doesn't support them)
            const codeWithoutImports = code.replace(/import\s+.*?from\s+['"].*?['"];?/g, '');
            
            // 2. Transpile JSX using Babel
            let compiledCode = codeWithoutImports;
            try {
                 compiledCode = Babel.transform(codeWithoutImports, {
                    presets: ['react', 'env'],
                    filename: 'dynamic.tsx',
                }).code || codeWithoutImports;
            } catch (babelErr) {
                console.warn("Babel transpilation failed, falling back to raw code:", babelErr);
            }

            const render = (Comp: any) => {
                if (typeof Comp === 'function') {
                    setComponent(<Comp data={data} images={images} />);
                } else {
                    setComponent(Comp);
                }
            };

            const scope = {
                React,
                antd,
                icons,
                ReactECharts, // Use static import
                render,
                data,
                images
            };

            const funcBody = `
                const { React, antd, icons, ReactECharts, render, data, images } = scope;
                try {
                    ${compiledCode}
                } catch (e) {
                    console.error("Component execution error:", e);
                    throw e;
                }
            `;

            // eslint-disable-next-line no-new-func
            const func = new Function('scope', funcBody);
            func(scope);
            setError(null);

        } catch (err: any) {
            console.error("Artifact Rendering Error:", err);
            setError(err.message || "Failed to render component");
        }
    }, [code, data, images]);

    const renderContent = () => (
        <Suspense fallback={
            <div style={{
                padding: 40, 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center', 
                color: 'var(--text-tertiary)'
            }}>
                <div style={{ 
                    width: 24, 
                    height: 24, 
                    border: '2px solid var(--primary-color)', 
                    borderTopColor: 'transparent', 
                    borderRadius: '50%', 
                    animation: 'spin 1s linear infinite',
                    marginBottom: 12
                }}></div>
                <span>渲染组件中...</span>
                <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            </div>
        }>
            {Component}
        </Suspense>
    );

    if (error) {
        return (
            <div style={{ 
                padding: '12px 16px', 
                background: '#fff1f0', 
                border: '1px solid #ffccc7', 
                borderRadius: 'var(--radius-md)', 
                color: '#cf1322',
                marginTop: 12,
                fontSize: 13
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <WarningOutlined /> <strong>组件渲染失败</strong>
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: 12, opacity: 0.8 }}>{error}</div>
            </div>
        );
    }

    return (
        <>
            <div 
                ref={containerRef} 
                className="artifact-card animate-slide-in"
            >
                <div className="artifact-header">
                     <Space>
                        <BarChartOutlined style={{ color: 'var(--primary-color)' }} />
                        <Typography.Text strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>分析结果</Typography.Text>
                     </Space>
                     <Space size="small">
                        <Tooltip title="全屏查看">
                            <Button 
                                type="text" 
                                icon={<FullscreenOutlined />} 
                                size="small" 
                                onClick={() => setIsFullscreen(true)}
                                className="action-btn"
                                style={{ color: 'var(--text-secondary)' }}
                            />
                        </Tooltip>
                     </Space>
                </div>
                
                <div style={{ padding: 20 }}>
                    {renderContent()}
                </div>
            </div>

            <Modal
                open={isFullscreen}
                onCancel={() => setIsFullscreen(false)}
                footer={null}
                width="95vw"
                style={{ top: 20 }}
                styles={{ body: { height: '90vh', overflow: 'auto', padding: 0 } }}
                closeIcon={<FullscreenExitOutlined style={{ color: '#fff', fontSize: 20, background: 'rgba(0,0,0,0.5)', padding: 8, borderRadius: '50%' }} />}
                wrapClassName="fullscreen-modal-wrap"
            >
                <div style={{ padding: 24, height: '100%', background: 'var(--bg-container)' }}>
                    {renderContent()}
                </div>
            </Modal>
        </>
    );
};

export default ArtifactRenderer;
