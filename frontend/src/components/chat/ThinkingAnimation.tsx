import React from 'react';
import { theme } from 'antd';

const { useToken } = theme;

interface ThinkingAnimationProps {
    isVisible: boolean;
}

const ThinkingAnimation: React.FC<ThinkingAnimationProps> = ({ isVisible }) => {
    const { token } = useToken();
    
    if (!isVisible) return null;

    return (
        <div style={{ display: 'inline-flex', alignItems: 'center', marginLeft: 8, verticalAlign: 'middle' }}>
            <div className="thinking-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
            <style>{`
                .thinking-dots {
                    display: flex;
                    gap: 3px;
                }
                .thinking-dots span {
                    width: 4px;
                    height: 4px;
                    background-color: ${token.colorTextSecondary};
                    border-radius: 50%;
                    animation: thinking-bounce 1.4s infinite ease-in-out both;
                }
                .thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
                .thinking-dots span:nth-child(2) { animation-delay: -0.16s; }
                @keyframes thinking-bounce {
                    0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
                    40% { transform: scale(1); opacity: 1; }
                }
            `}</style>
        </div>
    );
};

export default ThinkingAnimation;
