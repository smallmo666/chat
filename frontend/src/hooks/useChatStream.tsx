import { useState, useCallback, useRef } from 'react';
import { message } from 'antd';
import { SyncOutlined, LoadingOutlined } from '@ant-design/icons';
import { Tag } from 'antd';
import React from 'react';
import { ENDPOINTS } from '../config';
import type { Message, TaskItem } from '../types';

interface UseChatStreamProps {
    projectId?: string;
    threadId: string;
    onSessionCreated?: () => void;
}

export const useChatStream = ({ projectId, threadId, onSessionCreated }: UseChatStreamProps) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [tasks, setTasks] = useState<TaskItem[]>([
        { id: 'init', title: '等待输入...', status: 'pending' }
    ]);
    const [latestData, setLatestData] = useState<any[]>([]);
    const lastRequestRef = useRef<{ userMsg: string; checkedKeys: any[]; command: string; modifiedSql?: string } | null>(null);

    const updateStepStatus = useCallback((node: string, _status: string, details: string, duration?: number) => {
        // Update global tasks state
        setTasks(prev => {
            const newTasks = [...prev];
            const taskIndex = newTasks.findIndex(t => t.id === node);
            
            if (taskIndex !== -1) {
                // Keep description simple for data logic, UI can render Tag if needed
                // But since we are passing React Nodes in types, we keep it for now
                let desc: React.ReactNode = details || '完成';
                if (details && details.length > 50) {
                     // We can keep using Tag here as it's part of the TaskItem type definition which allows ReactNode
                     desc = <Tag color="blue" style={{whiteSpace: 'normal', wordBreak: 'break-all'}}>{details}</Tag>;
                }
                
                newTasks[taskIndex] = {
                    ...newTasks[taskIndex],
                    status: 'finish',
                    description: desc,
                    duration: duration
                };
                
                if (taskIndex + 1 < newTasks.length) {
                    if (newTasks[taskIndex + 1].status === 'pending') {
                        newTasks[taskIndex + 1].status = 'process';
                        newTasks[taskIndex + 1].description = <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag>;
                    }
                }
            }
            return newTasks;
        });

        // Also update the plan in the message history
        setMessages(prev => {
            const newMsgs = [...prev];
            // Reverse search for the plan message
            let planMsgIndex = -1;
            for (let i = newMsgs.length - 1; i >= 0; i--) {
                if (newMsgs[i].plan) {
                    planMsgIndex = i;
                    break;
                }
            }

            if (planMsgIndex !== -1) {
                const planMsg = { ...newMsgs[planMsgIndex] };
                const newPlan = [...(planMsg.plan || [])];
                const taskIndex = newPlan.findIndex(t => t.id === node);

                if (taskIndex !== -1) {
                    let desc: React.ReactNode = details || '完成';
                    if (details && details.length > 50) {
                         desc = <Tag color="blue" style={{whiteSpace: 'normal', wordBreak: 'break-all'}}>{details}</Tag>;
                    }

                    newPlan[taskIndex] = {
                        ...newPlan[taskIndex],
                        status: 'finish',
                        description: desc,
                        duration: duration
                    };

                    if (taskIndex + 1 < newPlan.length) {
                        if (newPlan[taskIndex + 1].status === 'pending') {
                            newPlan[taskIndex + 1].status = 'process';
                            newPlan[taskIndex + 1].description = <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag>;
                        }
                    }
                    
                    planMsg.plan = newPlan;
                    newMsgs[planMsgIndex] = planMsg;
                }
            }
            return newMsgs;
        });
    }, []);

    const sendMessage = useCallback(async (userMsg: string, checkedKeys: any[] = [], command: string = "start", modifiedSql?: string) => {
        const selectedTables = checkedKeys.filter(k => typeof k === 'string' && !k.toString().includes('.'));
        lastRequestRef.current = { userMsg, checkedKeys, command, modifiedSql };
        setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
        setIsLoading(true);
        setLatestData([]);
        setMessages(prev => [...prev, { role: 'agent', thinking: '', content: '' }]);
        setTasks([
          { id: 'planning', title: '正在规划...', status: 'process', description: <Tag color="processing" icon={<LoadingOutlined />}>AI 思考中</Tag> },
        ]);
        const token = localStorage.getItem('token');
        if (!token) {
            message.error('请先登录');
            setIsLoading(false);
            return;
        }
        const startStream = async (retry = false) => {
            const response = await fetch(ENDPOINTS.CHAT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                    ...(retry ? { 'X-Retry': '1' } : {})
                },
                body: JSON.stringify({ 
                    message: userMsg,
                    selected_tables: selectedTables.length > 0 ? selectedTables : undefined,
                    thread_id: threadId,
                    project_id: projectId ? parseInt(projectId) : undefined,
                    command,
                    modified_sql: modifiedSql
                }),
            });
            if (response.status === 401) {
                message.error('会话已过期，请重新登录');
                setIsLoading(false);
                return;
            }
            if (onSessionCreated) {
                setTimeout(onSessionCreated, 1000);
            }
            if (!response.body) return;
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let thinkingBuffer = '';
            let lastThinkingFlush = 0;
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    setIsLoading(false);
                    break;
                }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (!line.startsWith('event: ')) continue;
                    const eventType = line.split('\n')[0].replace('event: ', '').trim();
                    const dataStr = line.split('\n')[1]?.replace('data: ', '').trim();
                    if (!dataStr) continue;
                    try {
                        const data = JSON.parse(dataStr);
                        if (eventType === 'thinking') {
                            thinkingBuffer += data.content;
                            const now = performance.now();
                            if (now - lastThinkingFlush > 50) {
                                const chunk = thinkingBuffer;
                                thinkingBuffer = '';
                                lastThinkingFlush = now;
                                setMessages(prev => {
                                    const newMsgs = [...prev];
                                    const lastMsg = newMsgs[newMsgs.length - 1];
                                    if (lastMsg && lastMsg.role === 'agent') {
                                        newMsgs[newMsgs.length - 1] = {
                                            ...lastMsg,
                                            thinking: (lastMsg.thinking || '') + chunk
                                        };
                                    }
                                    return newMsgs;
                                });
                            }
                        } else if (eventType === 'plan') {
                            const newTasks: TaskItem[] = data.content.map((step: any, index: number) => ({
                                id: step.node,
                                title: step.desc,
                                status: index === 0 ? 'process' : 'pending',
                                description: index === 0 ? <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag> : '等待中',
                                logs: []
                            }));
                            setTasks(newTasks);
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastMsg = newMsgs[newMsgs.length - 1];
                                if (lastMsg && lastMsg.role === 'agent' && !lastMsg.content && !lastMsg.plan && !lastMsg.thinking) {
                                    newMsgs[newMsgs.length - 1] = { ...lastMsg, plan: newTasks };
                                } else {
                                    newMsgs.push({ role: 'agent', content: '', plan: newTasks });
                                }
                                return newMsgs;
                            });
                        } else if (eventType === 'step') {
                            updateStepStatus(data.node, data.status, data.details, data.duration);
                        } else if (eventType === 'interrupt') {
                            setMessages(prev => [...prev, { role: 'agent', content: data.content, interrupt: true }]);
                            setIsLoading(false);
                        } else if (eventType === 'detective_insight') {
                            const { hypotheses, depth } = data;
                            setMessages(prev => [...prev, { role: 'agent', content: '', hypotheses, analysisDepth: depth }]);
                        } else if (eventType === 'insight_mined') {
                            const insights = data.content;
                            setMessages(prev => [...prev, { role: 'agent', content: '', insights }]);
                        } else if (eventType === 'ui_generated') {
                            const code = data.content;
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastMsg = newMsgs[newMsgs.length - 1];
                                if (lastMsg && lastMsg.role === 'agent' && !lastMsg.uiComponent) {
                                    newMsgs[newMsgs.length - 1] = { ...lastMsg, uiComponent: code };
                                } else {
                                    newMsgs.push({ role: 'agent', content: '', uiComponent: code });
                                }
                                return newMsgs;
                            });
                        } else if (eventType === 'python_images') {
                            const images = data.content;
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastMsg = newMsgs[newMsgs.length - 1];
                                if (lastMsg && lastMsg.role === 'agent') {
                                    newMsgs[newMsgs.length - 1] = { ...lastMsg, images };
                                } else {
                                    newMsgs.push({ role: 'agent', content: '', images });
                                }
                                return newMsgs;
                            });
                        } else if (eventType === 'code_generated') {
                            const codeContent = `\`\`\`python\n${data.content}\n\`\`\``;
                            setMessages(prev => [...prev, { role: 'agent', content: codeContent, isCode: true }]);
                        } else if (eventType === 'result') {
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastMsg = newMsgs[newMsgs.length - 1];
                                if (lastMsg && lastMsg.role === 'agent') {
                                    let clarification = undefined;
                                    let content = data.content;
                                    try {
                                        if (typeof content === 'string' && (content.trim().startsWith('{') || content.trim().startsWith('```json'))) {
                                            const cleanContent = content.replace(/```json\n|\n```/g, '').trim();
                                            const parsed = JSON.parse(cleanContent);
                                            if (parsed.status === 'AMBIGUOUS') {
                                                clarification = parsed;
                                                content = ''; // Clear content so we don't show raw JSON
                                            }
                                        }
                                    } catch (e) {
                                        // Ignore parse error, treat as text
                                    }

                                    newMsgs[newMsgs.length - 1] = { 
                                        ...lastMsg, 
                                        content,
                                        clarification
                                    };
                                }
                                return newMsgs;
                            });
                        } else if (eventType === 'clarification') {
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastMsg = newMsgs[newMsgs.length - 1];
                                if (lastMsg && lastMsg.role === 'agent') {
                                    newMsgs[newMsgs.length - 1] = { 
                                        ...lastMsg, 
                                        clarification: data.content 
                                    };
                                } else {
                                    newMsgs.push({ role: 'agent', content: '', clarification: data.content });
                                }
                                return newMsgs;
                            });
                        } else if (eventType === 'data_export') {
                            setLatestData(data.content);
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastMsg = newMsgs[newMsgs.length - 1];
                                if (lastMsg && lastMsg.role === 'agent') {
                                    newMsgs[newMsgs.length - 1] = { ...lastMsg, data: data.content };
                                }
                                return newMsgs;
                            });
                        } else if (eventType === 'data_download') {
                            const token = data.content;
                            setMessages(prev => [...prev, { role: 'agent', content: '', downloadToken: token }]);
                        } else if (eventType === 'analysis') {
                            setMessages(prev => [...prev, { role: 'agent', content: data.content, isAnalysis: true }]);
                        } else if (eventType === 'visualization') {
                            const vizData = data.content;
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastMsg = newMsgs[newMsgs.length - 1];
                                if (lastMsg && lastMsg.role === 'agent' && !lastMsg.content && !lastMsg.thinking && !lastMsg.vizOption) {
                                    newMsgs[newMsgs.length - 1] = { ...lastMsg, vizOption: vizData.option || vizData };
                                } else {
                                    newMsgs.push({ role: 'agent', content: '', vizOption: vizData.option || vizData });
                                }
                                return newMsgs;
                            });
                            setIsLoading(false);
                        } else if (eventType === 'error') {
                            setMessages(prev => [...prev, { role: 'agent', content: `Error: ${data.content}` }]);
                            setIsLoading(false);
                        }
                    } catch (e) {
                        console.error("Failed to parse SSE data", e);
                    }
                }
            }
        };
        try {
            await startStream(false);
        } catch (error) {
            console.error('Stream error, retrying once:', error);
            try {
                await startStream(true);
            } catch (e) {
                console.error('Retry failed:', e);
                setMessages(prev => [...prev, { role: 'agent', content: '连接中断，请稍后重试。' }]);
            }
        } finally {
            setIsLoading(false);
        }
    }, [projectId, threadId, onSessionCreated, updateStepStatus]);

    return {
        messages,
        setMessages,
        isLoading,
        tasks,
        setTasks,
        sendMessage,
        latestData
    };
};
