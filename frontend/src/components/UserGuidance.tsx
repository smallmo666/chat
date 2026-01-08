import React, { useState, useEffect } from 'react';
import { Button, Space, Typography, Tour } from 'antd';
import type { TourProps } from 'antd';
import { 
    BulbOutlined, QuestionCircleOutlined, 
    ArrowRightOutlined, ArrowLeftOutlined, CheckOutlined
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';

const { Text, Title } = Typography;

interface UserGuidanceProps {
    isFirstTime?: boolean;
    onComplete?: () => void;
    className?: string;
}

interface GuidanceStep {
    title: string;
    description: string;
    target: string;
    placement?: 'top' | 'bottom' | 'left' | 'right';
    icon?: React.ReactNode;
}

const UserGuidance: React.FC<UserGuidanceProps> = ({ 
    isFirstTime = false, 
    onComplete,
    className = ''
}) => {
    const [currentStep, setCurrentStep] = useState(0);
    const [isVisible, setIsVisible] = useState(isFirstTime);
    const [tourOpen, setTourOpen] = useState(false);

    const guidanceSteps: GuidanceStep[] = [
        {
            title: "欢迎使用智能数据分析助手",
            description: "我可以帮助您分析数据、生成报告、创建可视化图表。让我们快速了解一下主要功能吧！",
            target: ".chat-header",
            placement: 'bottom',
            icon: <BulbOutlined />
        },
        {
            title: "输入您的问题",
            description: "在底部的输入框中输入您的数据分析需求，比如'分析销售趋势'或'生成月度报告'。",
            target: ".chat-input-area",
            placement: 'top',
            icon: <QuestionCircleOutlined />
        },
        {
            title: "查看分析结果",
            description: "我会为您提供详细的分析结果，包括数据洞察、可视化图表和代码示例。",
            target: ".message-container",
            placement: 'right',
            icon: <CheckOutlined />
        },
        {
            title: "交互式功能",
            description: "您可以点击代码编辑、下载结果、查看执行计划，或使用快捷操作按钮。",
            target: ".message-actions",
            placement: 'left',
            icon: <ArrowRightOutlined />
        }
    ];

    const handleNext = () => {
        if (currentStep < guidanceSteps.length - 1) {
            setCurrentStep(currentStep + 1);
        } else {
            handleComplete();
        }
    };

    const handlePrevious = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1);
        }
    };

    const handleSkip = () => {
        setIsVisible(false);
        localStorage.setItem('hasSeenGuidance', 'true');
        onComplete?.();
    };

    const handleComplete = () => {
        setIsVisible(false);
        localStorage.setItem('hasSeenGuidance', 'true');
        onComplete?.();
    };

    const startTour = () => {
        setTourOpen(true);
    };

    const tourSteps: TourProps['steps'] = guidanceSteps.map((step, index) => ({
        title: step.title,
        description: step.description,
        target: () => document.querySelector(step.target) as HTMLElement,
        placement: step.placement,
        nextButtonProps: {
            children: index === guidanceSteps.length - 1 ? '完成' : '下一步',
            icon: index === guidanceSteps.length - 1 ? <CheckOutlined /> : <ArrowRightOutlined />
        },
        prevButtonProps: {
            children: '上一步',
            icon: <ArrowLeftOutlined />
        }
    }));

    if (!isVisible) return null;

    return (
        <>
            <AnimatePresence>
                {isVisible && !tourOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className={`user-guidance-overlay ${className}`}
                        style={{
                            position: 'fixed',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            backgroundColor: 'rgba(0, 0, 0, 0.7)',
                            zIndex: 1000,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}
                    >
                        <motion.div
                            initial={{ scale: 0.9 }}
                            animate={{ scale: 1 }}
                            className="user-guidance-modal"
                            style={{
                                backgroundColor: 'var(--bg-container)',
                                borderRadius: 16,
                                padding: '32px',
                                maxWidth: '500px',
                                width: '90%',
                                boxShadow: 'var(--shadow-lg)',
                                border: '1px solid var(--border-color)'
                            }}
                        >
                            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                                <BulbOutlined 
                                    style={{ 
                                        fontSize: '48px', 
                                        color: 'var(--primary-color)', 
                                        marginBottom: '16px' 
                                    }} 
                                />
                                <Title level={3} style={{ margin: 0, color: 'var(--text-primary)' }}>
                                    欢迎使用智能助手
                                </Title>
                                <Text type="secondary" style={{ fontSize: '16px', marginTop: '8px' }}>
                                    让我们快速了解如何使用这个强大的工具
                                </Text>
                            </div>

                            <div style={{ marginBottom: '24px' }}>
                                {guidanceSteps.map((step, index) => (
                                    <div 
                                        key={index}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            padding: '12px',
                                            marginBottom: '8px',
                                            backgroundColor: index === currentStep ? 'var(--primary-bg)' : 'transparent',
                                            borderRadius: '8px',
                                            border: index === currentStep ? '1px solid var(--primary-color)' : 'none',
                                            transition: 'all 0.3s ease'
                                        }}
                                    >
                                        <div style={{
                                            width: '32px',
                                            height: '32px',
                                            borderRadius: '50%',
                                            backgroundColor: 'var(--primary-color)',
                                            color: 'white',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            marginRight: '12px',
                                            fontSize: '14px',
                                            fontWeight: 'bold'
                                        }}>
                                            {index + 1}
                                        </div>
                                        <div style={{ flex: 1 }}>
                                            <Text strong style={{ color: 'var(--text-primary)' }}>
                                                {step.title}
                                            </Text>
                                            <br />
                                            <Text type="secondary" style={{ fontSize: '14px' }}>
                                                {step.description}
                                            </Text>
                                        </div>
                                        {step.icon}
                                    </div>
                                ))}
                            </div>

                            <Space size="middle" style={{ width: '100%', justifyContent: 'center' }}>
                                <Button onClick={handleSkip}>
                                    跳过引导
                                </Button>
                                <Button type="primary" onClick={startTour}>
                                    开始体验
                                </Button>
                            </Space>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            <Tour
                open={tourOpen}
                onClose={() => setTourOpen(false)}
                steps={tourSteps}
                indicatorsRender={(current, total) => (
                    <span style={{ color: 'var(--text-secondary)' }}>
                        {current + 1} / {total}
                    </span>
                )}
                onFinish={handleComplete}
            />
        </>
    );
};

// Hook to check if user needs guidance
export const useUserGuidance = () => {
    const [needsGuidance, setNeedsGuidance] = useState(false);

    useEffect(() => {
        const hasSeenGuidance = localStorage.getItem('hasSeenGuidance');
        const isFirstVisit = !hasSeenGuidance || hasSeenGuidance === 'false';
        setNeedsGuidance(isFirstVisit);
    }, []);

    return { needsGuidance };
};

export default UserGuidance;
