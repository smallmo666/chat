import React from 'react';
import { motion } from 'framer-motion';

interface MessageAnimationProps {
    children: React.ReactNode;
}

const MessageAnimation: React.FC<MessageAnimationProps> = ({ children }) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            style={{ width: '100%' }}
        >
            {children}
        </motion.div>
    );
};

export default MessageAnimation;
