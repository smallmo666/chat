import React, { useEffect, useRef, useState } from 'react';

interface AccessibilityWrapperProps {
    children: React.ReactNode;
    role?: string;
    ariaLabel?: string;
    ariaDescribedBy?: string;
    ariaExpanded?: boolean;
    ariaControls?: string;
    tabIndex?: number;
    onKeyDown?: (event: React.KeyboardEvent) => void;
    className?: string;
    style?: React.CSSProperties;
}

const AccessibilityWrapper = React.forwardRef<HTMLDivElement, AccessibilityWrapperProps>(({
    children,
    role,
    ariaLabel,
    ariaDescribedBy,
    ariaExpanded,
    ariaControls,
    tabIndex,
    onKeyDown,
    className,
    style
}, ref) => {
    return (
        <div
            ref={ref}
            role={role}
            aria-label={ariaLabel}
            aria-describedby={ariaDescribedBy}
            aria-expanded={ariaExpanded}
            aria-controls={ariaControls}
            tabIndex={tabIndex}
            onKeyDown={onKeyDown}
            className={className}
            style={style}
        >
            {children}
        </div>
    );
});

AccessibilityWrapper.displayName = 'AccessibilityWrapper';

// 键盘导航hook
export const useKeyboardNavigation = (ref: React.RefObject<HTMLElement>) => {
    useEffect(() => {
        const element = ref.current;
        if (!element) return;

        const handleKeyDown = (event: KeyboardEvent) => {
            const focusableElements = element.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            
            const currentFocus = document.activeElement as HTMLElement;
            const currentIndex = Array.from(focusableElements).indexOf(currentFocus);

            switch (event.key) {
                case 'ArrowDown':
                case 'ArrowRight':
                    event.preventDefault();
                    const nextIndex = (currentIndex + 1) % focusableElements.length;
                    (focusableElements[nextIndex] as HTMLElement).focus();
                    break;
                case 'ArrowUp':
                case 'ArrowLeft':
                    event.preventDefault();
                    const prevIndex = currentIndex <= 0 ? focusableElements.length - 1 : currentIndex - 1;
                    (focusableElements[prevIndex] as HTMLElement).focus();
                    break;
                case 'Home':
                    event.preventDefault();
                    (focusableElements[0] as HTMLElement).focus();
                    break;
                case 'End':
                    event.preventDefault();
                    (focusableElements[focusableElements.length - 1] as HTMLElement).focus();
                    break;
                case 'Escape':
                    // 处理ESC键逻辑
                    break;
            }
        };

        element.addEventListener('keydown', handleKeyDown);
        return () => element.removeEventListener('keydown', handleKeyDown);
    }, []);
};

// 屏幕阅读器通知hook
export const useScreenReaderNotification = () => {
    const createNotification = (message: string, priority: 'polite' | 'assertive' = 'polite') => {
        const notification = document.createElement('div');
        notification.setAttribute('role', 'status');
        notification.setAttribute('aria-live', priority);
        notification.setAttribute('aria-atomic', 'true');
        notification.style.position = 'absolute';
        notification.style.left = '-10000px';
        notification.style.width = '1px';
        notification.style.height = '1px';
        notification.style.overflow = 'hidden';
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 1000);
    };

    return { notify: createNotification };
};

// 焦点管理hook
export const useFocusManagement = () => {
    const focusRef = useRef<HTMLElement | null>(null);

    const setFocus = (element: HTMLElement | null) => {
        focusRef.current = element;
        element?.focus();
    };

    const restoreFocus = () => {
        if (focusRef.current) {
            focusRef.current.focus();
        }
    };

    return { setFocus, restoreFocus };
};

// 高对比度模式支持
export const useHighContrastMode = () => {
    const [isHighContrast, setIsHighContrast] = useState(false);

    useEffect(() => {
        const checkHighContrast = () => {
            const mediaQuery = window.matchMedia('(prefers-contrast: high)');
            setIsHighContrast(mediaQuery.matches);
        };

        checkHighContrast();
        const mediaQuery = window.matchMedia('(prefers-contrast: high)');
        mediaQuery.addEventListener('change', checkHighContrast);

        return () => mediaQuery.removeEventListener('change', checkHighContrast);
    }, []);

    return isHighContrast;
};

// 减少动画偏好支持
export const useReducedMotion = () => {
    const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

    useEffect(() => {
        const checkReducedMotion = () => {
            const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
            setPrefersReducedMotion(mediaQuery.matches);
        };

        checkReducedMotion();
        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        mediaQuery.addEventListener('change', checkReducedMotion);

        return () => mediaQuery.removeEventListener('change', checkReducedMotion);
    }, []);

    return prefersReducedMotion;
};

export default AccessibilityWrapper;