import React, { useEffect, useRef, useState, Suspense } from 'react';
import * as antd from 'antd';
import * as icons from '@ant-design/icons';
const LazyECharts = React.lazy(() => import('echarts-for-react'));

interface ArtifactRendererProps {
    code: string;
    data: any;
    images?: string[];
}

const ArtifactRenderer: React.FC<ArtifactRendererProps> = ({ code, data, images }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [error, setError] = useState<string | null>(null);
    const [Component, setComponent] = useState<React.ReactNode | null>(null);

    useEffect(() => {
        if (!code) return;

        try {
            // 定义 render 函数，供组件代码调用
            const render = (Comp: any) => {
                if (typeof Comp === 'function') {
                    // Inject images into props
                    setComponent(<Comp data={data} images={images} />);
                } else {
                    setComponent(Comp);
                }
            };

            // 构建沙箱环境
            const scope = {
                React,
                antd,
                icons,
                ReactECharts: LazyECharts,
                render,
                data, // 也将 data 直接暴露给 scope，虽然通常通过 props 传递
                images
            };

            // 构造函数体
            // 假设 code 包含组件定义和 render(Component) 调用
            const funcBody = `
                const { React, antd, icons, ReactECharts, render, data, images } = scope;
                try {
                    ${code}
                } catch (e) {
                    console.error("Component execution error:", e);
                    throw e;
                }
            `;

            // 执行
            // eslint-disable-next-line no-new-func
            const func = new Function('scope', funcBody);
            func(scope);
            setError(null);

        } catch (err: any) {
            console.error("Artifact Rendering Error:", err);
            setError(err.message || "Failed to render component");
        }
    }, [code, data]);

    if (error) {
        return (
            <div style={{ padding: 16, background: '#fff1f0', border: '1px solid #ffccc7', borderRadius: 8, color: '#cf1322' }}>
                <strong>渲染错误:</strong> {error}
                <pre style={{ marginTop: 8, fontSize: 12, overflowX: 'auto' }}>{code}</pre>
            </div>
        );
    }

    return (
        <div ref={containerRef} style={{ border: '1px solid #f0f0f0', borderRadius: 8, padding: 16, marginTop: 16, background: '#fafafa' }}>
            <Suspense fallback={<div style={{color:'#999'}}>加载图表组件...</div>}>
                {Component}
            </Suspense>
        </div>
    );
};

export default ArtifactRenderer;
