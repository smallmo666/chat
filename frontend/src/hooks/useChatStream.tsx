import { useState, useCallback, useRef } from 'react';
import { message } from 'antd';
import { SyncOutlined, LoadingOutlined } from '@ant-design/icons';
import { Tag } from 'antd';
import React from 'react';
import { ENDPOINTS } from '../config';
import type { Message, TaskItem } from '../chatTypes';

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
                let desc: React.ReactNode = details || '完成';
                if (details && details.length > 50) {
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
            const lastMsg = newMsgs[newMsgs.length - 1];
            if (lastMsg && lastMsg.role === 'agent') {
                 const planMsg = { ...lastMsg };
                 if (planMsg.plan) {
                    const newPlan = [...planMsg.plan];
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
                        newMsgs[newMsgs.length - 1] = planMsg;
                    }
                 }
            }
            return newMsgs;
        });
    }, []);

    const sendMessage = useCallback(async (userMsg: string, checkedKeys: any[] = [], command: string = "start", modifiedSql?: string) => {
        const selectedTables = checkedKeys.filter(k => typeof k === 'string' && !k.toString().includes('.'));
        lastRequestRef.current = { userMsg, checkedKeys, command, modifiedSql };
        
        if (command !== 'clarify' && userMsg && userMsg.trim().length > 0) {
            setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
        }
        
        setIsLoading(true);
        setLatestData([]);
        
        // Add Agent Placeholder Message
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
                    message: command === 'clarify' ? '' : userMsg,
                    selected_tables: command === 'clarify' ? undefined : (selectedTables.length > 0 ? selectedTables : undefined),
                    clarify_choices: command === 'clarify' ? checkedKeys.filter(k => typeof k === 'string') : undefined,
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
                        
                        // Helper to update the last agent message
                        const updateLastAgentMessage = (updater: (msg: Message) => Message) => {
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastIndex = newMsgs.length - 1;
                                if (lastIndex >= 0 && newMsgs[lastIndex].role === 'agent') {
                                    newMsgs[lastIndex] = updater(newMsgs[lastIndex]);
                                }
                                return newMsgs;
                            });
                        };

                        if (eventType === 'thinking') {
                            thinkingBuffer += data.content;
                            const now = performance.now();
                            if (now - lastThinkingFlush > 50) {
                                const chunk = thinkingBuffer;
                                thinkingBuffer = '';
                                lastThinkingFlush = now;
                                updateLastAgentMessage(msg => ({
                                    ...msg,
                                    thinking: (msg.thinking || '') + chunk
                                }));
                            }
                        } else if (eventType === 'plan') {
                            const newTasks: TaskItem[] = data.content.map((step: any, index: number) => ({
                                id: step.node,
                                title: step.desc,
                                status: index === 0 ? 'process' : 'pending',
                                description: index === 0 ? <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag> : '等待中',
                                logs: [],
                                subtasks: []
                            }));
                            setTasks(newTasks);
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                plan: newTasks,
                                currentTask: newTasks[0]?.title
                            }));
                        } else if (eventType === 'substep') {
                            const { node, step, detail, ts } = data;
                            // Update global tasks
                            setTasks(prev => {
                                const newTasks = [...prev];
                                const taskIndex = newTasks.findIndex(t => t.id === node);
                                if (taskIndex !== -1) {
                                    const currentTask = newTasks[taskIndex];
                                    const newSubtasks = [...(currentTask.subtasks || [])];
                                    newSubtasks.push({
                                        id: `${node}-${step}-${ts}`,
                                        title: step,
                                        status: 'finish',
                                        description: detail,
                                        startTime: ts,
                                        endTime: ts,
                                        duration: 0
                                    });
                                    newTasks[taskIndex] = { ...currentTask, subtasks: newSubtasks };
                                }
                                return newTasks;
                            });

                            // Update message plan
                            updateLastAgentMessage(msg => {
                                const newPlan = msg.plan ? [...msg.plan] : [];
                                const taskIndex = newPlan.findIndex(t => t.id === node);
                                let currentTaskTitle = msg.currentTask;

                                if (taskIndex !== -1) {
                                    const currentTask = newPlan[taskIndex];
                                    currentTaskTitle = `${currentTask.title}: ${step}`;
                                    const newSubtasks = [...(currentTask.subtasks || [])];
                                    newSubtasks.push({
                                        id: `${node}-${step}-${ts}`,
                                        title: step,
                                        status: 'finish',
                                        description: detail,
                                        startTime: ts,
                                        endTime: ts,
                                        duration: 0
                                    });
                                    newPlan[taskIndex] = { ...currentTask, subtasks: newSubtasks };
                                }
                                const newLogs = [...(msg.actionLogs || [])];
                                newLogs.push({ node, step, detail, ts });
                                return { ...msg, plan: newPlan, actionLogs: newLogs, currentTask: currentTaskTitle };
                            });

                        } else if (eventType === 'step') {
                            const { node, status, details, duration } = data;
                            updateStepStatus(node, status, details, duration);
                            
                            // Also update currentTask for the next step
                            if (status === 'completed') {
                                updateLastAgentMessage(msg => {
                                    const nextIndex = (msg.plan?.findIndex(t => t.id === node) ?? -1) + 1;
                                    const nextTask = msg.plan?.[nextIndex];
                                    return {
                                        ...msg,
                                        currentTask: nextTask ? nextTask.title : undefined
                                    };
                                });
                            }
                        } else if (eventType === 'interrupt') {
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                content: data.content,
                                interrupt: true
                            }));
                            setIsLoading(false);
                        } else if (eventType === 'detective_insight') {
                            const { hypotheses, depth } = data;
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                detectiveInsight: { hypotheses, depth } // Use object structure as per Message type
                            }));
                        } else if (eventType === 'insight_mined') {
                            const insights = data.content;
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                insights
                            }));
                        } else if (eventType === 'ui_generated') {
                            const code = data.content;
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                uiComponent: code
                            }));
                        } else if (eventType === 'python_images') {
                            const images = data.content;
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                images
                            }));
                        } else if (eventType === 'code_generated') {
                            const codeContent = `\`\`\`python\n${data.content}\n\`\`\``;
                             updateLastAgentMessage(msg => ({
                                ...msg,
                                content: (msg.content || '') + '\n\n' + codeContent, // Append code to content? Or use isCode?
                                isCode: true
                            }));
                            // Actually, if we append to content, it might duplicate if we also use 'content' event.
                            // But usually code_generated is separate. 
                            // Let's stick to appending or storing in a separate field if needed.
                            // The original code created a NEW message for code.
                            // To keep single bubble, we can append to `content`.
                        } else if (eventType === 'result') {
                            updateLastAgentMessage(msg => {
                                let clarification = msg.clarification;
                                let content = data.content;
                                try {
                                    if (typeof content === 'string') {
                                        const trimmed = content.trim();
                                        let jsonStr: string | null = null;
                                        if (trimmed.startsWith('```json')) {
                                            jsonStr = trimmed.replace(/```json\s*|\s*```/g, '').trim();
                                        } else if (trimmed.startsWith('{')) {
                                            jsonStr = trimmed;
                                        } else {
                                            const match = trimmed.match(/\{[\s\S]*\}/);
                                            jsonStr = match ? match[0] : null;
                                        }
                                        if (jsonStr) {
                                            const parsed = JSON.parse(jsonStr);
                                            if (parsed.status === 'AMBIGUOUS') {
                                                const scope =
                                                    parsed.scope === 'task' || parsed.scope === 'schema' || parsed.scope === 'param'
                                                        ? parsed.scope
                                                        : undefined;
                                                const parsedType: 'select' | 'multiple' = parsed.type === 'multiple' ? 'multiple' : 'select';
                                                const parsedClarification = {
                                                    question: typeof parsed.question === 'string' ? parsed.question : '',
                                                    options: Array.isArray(parsed.options) ? parsed.options : [],
                                                    type: parsedType,
                                                    scope
                                                };

                                                if (clarification) {
                                                    const existingOptions = Array.isArray(clarification.options) ? clarification.options : [];
                                                    const nextOptions = parsedClarification.options.length > 0 ? parsedClarification.options : existingOptions;
                                                    clarification = {
                                                        ...clarification,
                                                        ...parsedClarification,
                                                        question: parsedClarification.question || clarification.question,
                                                        options: nextOptions,
                                                        type: parsedClarification.type ?? clarification.type
                                                    };
                                                    content = '';
                                                } else if (parsedClarification.question || parsedClarification.options.length > 0) {
                                                    clarification = {
                                                        question: parsedClarification.question,
                                                        options: parsedClarification.options,
                                                        type: parsedClarification.type,
                                                        scope: parsedClarification.scope
                                                    };
                                                    content = '';
                                                }
                                            }
                                        }
                                    }
                                } catch (e) {
                                    // Ignore parse error
                                }
                                return {
                                    ...msg,
                                    content,
                                    clarification
                                };
                            });
                        } else if (eventType === 'clarification') {
                             updateLastAgentMessage(msg => ({
                                ...msg,
                                clarification: data.content
                            }));
                        } else if (eventType === 'data_export') {
                            setLatestData(data.content);
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                data: data.content
                            }));
                        } else if (eventType === 'data_download') {
                            const token = data.content;
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                downloadToken: token
                            }));
                        } else if (eventType === 'analysis') {
                            updateLastAgentMessage(msg => ({
                                ...msg,
                                content: (msg.content || '') + '\n\n' + data.content,
                                isAnalysis: true
                            }));
                        } else if (eventType === 'visualization') {
                            const vizData = data.content;
                            updateLastAgentMessage(msg => {
                                if (vizData && vizData.chart_type === 'echarts' && vizData.option) {
                                    return { ...msg, vizOption: vizData.option, tableData: undefined };
                                }
                                if (vizData && vizData.chart_type === 'table' && vizData.table_data) {
                                    return { ...msg, tableData: vizData.table_data, vizOption: undefined };
                                }
                                return { ...msg, vizOption: vizData.option || vizData };
                            });
                            setIsLoading(false);
                        } else if (eventType === 'error') {
                             updateLastAgentMessage(msg => ({
                                ...msg,
                                content: (msg.content || '') + `\n\nError: ${data.content}`
                            }));
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
        setIsLoading,
        tasks,
        setTasks,
        sendMessage,
        latestData
    };
};
