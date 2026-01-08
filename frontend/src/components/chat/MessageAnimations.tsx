import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// 自定义hook用于检测减少动画偏好
const useReducedMotion = () => {
    const [prefersReducedMotion, setPrefersReducedMotion] = React.useState(false);

    React.useEffect(() => {
        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        setPrefersReducedMotion(mediaQuery.matches);
        
        const handleChange = (e: MediaQueryListEvent) => {
            setPrefersReducedMotion(e.matches);
        };
        
        mediaQuery.addEventListener('change', handleChange);
        return () => mediaQuery.removeEventListener('change', handleChange);
    }, []);

    return prefersReducedMotion;
};

interface MessageAnimationProps {
    children: React.ReactNode;
    isUser?: boolean;
    isVisible?: boolean;
    delay?: number;
}

export const MessageAnimation: React.FC<MessageAnimationProps> = ({ 
    children, 
    isUser = false, 
    isVisible = true,
    delay = 0 
}) => {
    const prefersReducedMotion = useReducedMotion();
    
    if (prefersReducedMotion) {
        return <>{children}</>;
    }

    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ 
                        opacity: 0, 
                        y: 20, 
                        scale: 0.95,
                        x: isUser ? 20 : -20
                    }}
                    animate={{ 
                        opacity: 1, 
                        y: 0, 
                        scale: 1,
                        x: 0
                    }}
                    exit={{ 
                        opacity: 0, 
                        y: -10,
                        scale: 0.9
                    }}
                    transition={{ 
                        duration: 0.3,
                        delay,
                        ease: [0.16, 1, 0.3, 1]
                    }}
                >
                    {children}
                </motion.div>
            )}
        </AnimatePresence>
    );
};

interface ThinkingAnimationProps {
    isVisible?: boolean;
}

export const ThinkingAnimation: React.FC<ThinkingAnimationProps> = ({ isVisible = true }) => {
    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    className="thinking-animation"
                >
                    <motion.div
                        animate={{ 
                            rotate: 360,
                            scale: [1, 1.1, 1]
                        }}
                        transition={{ 
                            rotate: { duration: 2, repeat: Infinity, ease: "linear" },
                            scale: { duration: 1, repeat: Infinity, ease: "easeInOut" }
                        }}
                        style={{
                            width: 24,
                            height: 24,
                            border: '2px solid var(--primary-color)',
                            borderTop: '2px solid transparent',
                            borderRadius: '50%',
                            display: 'inline-block'
                        }}
                    />
                    <motion.span
                        animate={{ opacity: [0.5, 1, 0.5] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        style={{ marginLeft: 8, fontSize: 14, color: 'var(--text-secondary)' }}
                    >
                        正在思考...
                    </motion.span>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

interface TypingAnimationProps {
    text: string;
    speed?: number;
    onComplete?: () => void;
}

export const TypingAnimation: React.FC<TypingAnimationProps> = ({ 
    text, 
    speed = 30,
    onComplete 
}) => {
    const [displayText, setDisplayText] = React.useState('');
    const [currentIndex, setCurrentIndex] = React.useState(0);

    React.useEffect(() => {
        if (currentIndex < text.length) {
            const timer = setTimeout(() => {
                setDisplayText(prev => prev + text[currentIndex]);
                setCurrentIndex(prev => prev + 1);
            }, speed);
            return () => clearTimeout(timer);
        } else {
            onComplete?.();
        }
    }, [currentIndex, text, speed, onComplete]);

    return (
        <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
        >
            {displayText}
            <motion.span
                animate={{ opacity: [1, 0, 1] }}
                transition={{ duration: 0.8, repeat: Infinity }}
                style={{ fontWeight: 'bold', color: 'var(--primary-color)' }}
            >
                {currentIndex < text.length ? '▋' : ''}
            </motion.span>
        </motion.span>
    );
};

interface HoverCardProps {
    children: React.ReactNode;
    scale?: number;
    whileHover?: object;
    className?: string;
}

export const HoverCard: React.FC<HoverCardProps> = ({ 
    children, 
    scale = 1.02,
    whileHover,
    className = ''
}) => {
    return (
        <motion.div
            className={className}
            whileHover={{
                scale,
                y: -2,
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
                ...whileHover
            }}
            transition={{ duration: 0.2, ease: "easeOut" }}
        >
            {children}
        </motion.div>
    );
};

export default {
    MessageAnimation,
    ThinkingAnimation,
    TypingAnimation,
    HoverCard
};