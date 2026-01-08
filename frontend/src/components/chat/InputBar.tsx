import React, { useState, useRef, useEffect } from 'react';
import { Button, Input, Tooltip, App, theme } from 'antd';
import { SendOutlined, AudioOutlined, AudioFilled, StopOutlined } from '@ant-design/icons';

const { TextArea } = Input;

interface InputBarProps {
    onSend: (msg: string) => void;
    onStop?: () => void;
    isLoading: boolean;
    isReviewOpen: boolean;
    isDarkMode?: boolean;
}

const InputBar: React.FC<InputBarProps> = ({ onSend, onStop, isLoading, isReviewOpen, isDarkMode }) => {
    const { message } = App.useApp();
    const { token } = theme.useToken();
    const [inputValue, setInputValue] = useState('');
    const [isRecording, setIsRecording] = useState(false);
    const [isFocused, setIsFocused] = useState(false);
    const recognitionRef = useRef<any>(null);

    // Initialize Speech Recognition
    useEffect(() => {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = false;
            recognitionRef.current.lang = 'zh-CN';

            recognitionRef.current.onresult = (event: any) => {
                const transcript = event.results[0][0].transcript;
                setInputValue(prev => prev + transcript);
                setIsRecording(false);
            };

            recognitionRef.current.onerror = (event: any) => {
                console.error('Speech recognition error', event.error);
                setIsRecording(false);
                message.error('语音识别出错: ' + event.error);
            };

            recognitionRef.current.onend = () => {
                setIsRecording(false);
            };
        }

        // Keyboard Shortcuts
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                const textarea = document.querySelector('textarea');
                if (textarea) textarea.focus();
            }
            if (e.key === 'Escape' && inputValue) {
                e.preventDefault();
                setInputValue('');
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [inputValue]); 

    const toggleRecording = () => {
        if (!recognitionRef.current) {
            message.warning('您的浏览器不支持语音识别');
            return;
        }

        if (isRecording) {
            recognitionRef.current.stop();
        } else {
            try {
                recognitionRef.current.start();
                setIsRecording(true);
                message.info('请开始说话...');
            } catch (e) {
                console.error(e);
            }
        }
    };

    const handleSend = () => {
        if (isReviewOpen) return;
        if (isLoading) {
            handleStop();
            return;
        }
        if (!inputValue.trim()) return;
        onSend(inputValue);
        setInputValue('');
    };

    const handleStop = () => {
        if (onStop) {
            onStop();
        }
    };

    return (
        <div style={{ 
            position: 'absolute', 
            bottom: 0, 
            left: 0, 
            right: 0, 
            padding: '24px 32px 32px', 
            background: isDarkMode 
                ? 'linear-gradient(to top, rgba(20,20,20,1) 0%, rgba(20,20,20,0.8) 50%, rgba(20,20,20,0) 100%)' 
                : 'linear-gradient(to top, rgba(245,247,250,1) 0%, rgba(245,247,250,0.8) 50%, rgba(245,247,250,0) 100%)',
            zIndex: 20,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            pointerEvents: 'none' // Let clicks pass through transparent areas
        }}>
            <div 
                className={`glass-panel ${isFocused ? 'focused' : ''}`}
                style={{ 
                    display: 'flex', 
                    gap: 12, 
                    alignItems: 'flex-end', 
                    padding: '12px 12px 12px 20px', 
                    borderRadius: 24, 
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    width: '100%',
                    maxWidth: 900,
                    pointerEvents: 'auto', // Re-enable clicks
                    border: isFocused ? `1px solid ${token.colorPrimary}` : '1px solid rgba(255,255,255,0.5)',
                    boxShadow: isFocused ? `0 8px 32px ${token.colorPrimary}30` : 'var(--shadow-lg)',
                    transform: isFocused ? 'translateY(-2px)' : 'translateY(0)',
                    background: isDarkMode ? 'rgba(30,30,30,0.8)' : 'rgba(255,255,255,0.8)'
                }}
            >
                <TextArea 
                    value={inputValue}
                    onChange={e => setInputValue(e.target.value)}
                    onFocus={() => setIsFocused(true)}
                    onBlur={() => setIsFocused(false)}
                    onPressEnter={(e) => {
                        if (!e.shiftKey) {
                            e.preventDefault();
                            handleSend();
                        }
                    }}
                    placeholder="✨ 问点什么... (例如：统计上个月的订单趋势)" 
                    autoSize={{ minRows: 1, maxRows: 6 }}
                    disabled={isLoading || isReviewOpen}
                    style={{ 
                        padding: '8px 0', 
                        resize: 'none', 
                        border: 'none', 
                        boxShadow: 'none', 
                        background: 'transparent',
                        fontSize: 16,
                        lineHeight: 1.6,
                        color: 'var(--text-primary)',
                        caretColor: token.colorPrimary
                    }}
                />
                
                <div style={{display: 'flex', gap: 8, alignItems: 'center', paddingBottom: 2}}>
                        <Tooltip title={isRecording ? "点击停止" : "点击说话"}>
                        <Button 
                            type={isRecording ? 'primary' : 'text'}
                            danger={isRecording}
                            shape="circle"
                            size="large"
                            icon={isRecording ? <AudioFilled spin /> : <AudioOutlined />} 
                            onClick={toggleRecording}
                            className={isRecording ? 'recording-pulse' : ''}
                            style={{ 
                                color: isRecording ? '#fff' : 'var(--text-secondary)',
                                transition: 'all 0.2s',
                                border: 'none'
                            }}
                        />
                    </Tooltip>
                    
                    <Tooltip title={isLoading ? "点击暂停生成" : "发送消息"}>
                        <Button 
                            type="primary" 
                            shape="circle"
                            size="large"
                            icon={isLoading ? <StopOutlined /> : <SendOutlined />} 
                            onClick={handleSend}
                            disabled={isReviewOpen}
                            style={{ 
                                flexShrink: 0, 
                                width: 48, 
                                height: 48,
                                boxShadow: isLoading ? '0 4px 14px rgba(255, 77, 79, 0.4)' : `0 4px 14px ${token.colorPrimary}60`,
                                border: 'none',
                                background: isLoading 
                                    ? 'linear-gradient(135deg, #ff4d4f 0%, #cf1322 100%)'
                                    : `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryActive} 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                            }}
                        />
                    </Tooltip>
                </div>
            </div>
            
            <div style={{ 
                textAlign: 'center', 
                marginTop: 12, 
                color: 'var(--text-tertiary)', 
                fontSize: 12, 
                fontWeight: 500, 
                opacity: 0.8,
                pointerEvents: 'auto'
            }}>
                AI 生成内容仅供参考，请核对重要信息
            </div>

            <style>{`
                .recording-pulse {
                    animation: pulse-red 1.5s infinite;
                }
                @keyframes pulse-red {
                    0% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0.4); }
                    70% { box-shadow: 0 0 0 10px rgba(255, 77, 79, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0); }
                }
            `}</style>
        </div>
    );
};

export default InputBar;
