import React, { useState, useEffect } from 'react';

interface ResponsiveLayoutProps {
    children: React.ReactNode;
    breakpoints?: {
        xs?: number;
        sm?: number;
        md?: number;
        lg?: number;
        xl?: number;
    };
}

const ResponsiveLayout: React.FC<ResponsiveLayoutProps> = ({ 
    children, 
    breakpoints = { xs: 480, sm: 576, md: 768, lg: 992, xl: 1200 }
}) => {
    const [screenSize, setScreenSize] = useState<'xs' | 'sm' | 'md' | 'lg' | 'xl'>('md');
    const [isMounted, setIsMounted] = useState(false);

    useEffect(() => {
        setIsMounted(true);
        const handleResize = () => {
            const width = window.innerWidth;
            if (width < breakpoints.xs!) setScreenSize('xs');
            else if (width < breakpoints.sm!) setScreenSize('sm');
            else if (width < breakpoints.md!) setScreenSize('md');
            else if (width < breakpoints.lg!) setScreenSize('lg');
            else setScreenSize('xl');
        };

        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [breakpoints]);

    const getResponsiveStyles = () => {
        const baseStyles = {
            transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            willChange: 'transform, opacity'
        };

        switch (screenSize) {
            case 'xs':
                return {
                    ...baseStyles,
                    padding: '8px',
                    fontSize: '14px',
                    gap: '8px'
                };
            case 'sm':
                return {
                    ...baseStyles,
                    padding: '12px',
                    fontSize: '14px',
                    gap: '12px'
                };
            case 'md':
                return {
                    ...baseStyles,
                    padding: '16px',
                    fontSize: '15px',
                    gap: '16px'
                };
            case 'lg':
                return {
                    ...baseStyles,
                    padding: '20px',
                    fontSize: '15px',
                    gap: '20px'
                };
            case 'xl':
                return {
                    ...baseStyles,
                    padding: '24px',
                    fontSize: '16px',
                    gap: '24px'
                };
            default:
                return baseStyles;
        }
    };

    if (!isMounted) {
        return null; // 避免服务端渲染不匹配
    }

    return (
        <div 
            className={`responsive-layout responsive-${screenSize}`}
            style={getResponsiveStyles()}
            data-screen-size={screenSize}
        >
            {children}
        </div>
    );
};

// 自定义hook用于响应式逻辑
export const useResponsive = () => {
    const [screenSize, setScreenSize] = useState<'xs' | 'sm' | 'md' | 'lg' | 'xl'>('md');
    const [isMobile, setIsMobile] = useState(false);
    const [isTablet, setIsTablet] = useState(false);
    const [isDesktop, setIsDesktop] = useState(true);

    useEffect(() => {
        const handleResize = () => {
            const width = window.innerWidth;
            let size: 'xs' | 'sm' | 'md' | 'lg' | 'xl' = 'md';
            
            if (width < 480) size = 'xs';
            else if (width < 576) size = 'sm';
            else if (width < 768) size = 'md';
            else if (width < 992) size = 'lg';
            else size = 'xl';

            setScreenSize(size);
            setIsMobile(size === 'xs' || size === 'sm');
            setIsTablet(size === 'md');
            setIsDesktop(size === 'lg' || size === 'xl');
        };

        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    return {
        screenSize,
        isMobile,
        isTablet,
        isDesktop,
        isTouch: isMobile || isTablet
    };
};

export default ResponsiveLayout;