import React from 'react';

interface AccessibilityWrapperProps {
    children: React.ReactNode;
    role?: string;
    ariaLabel?: string;
}

const AccessibilityWrapper: React.FC<AccessibilityWrapperProps> = ({ 
    children, 
    role, 
    ariaLabel 
}) => {
    return (
        <div role={role} aria-label={ariaLabel} style={{ width: '100%' }}>
            {children}
        </div>
    );
};

export default AccessibilityWrapper;
