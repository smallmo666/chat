import React from 'react';
import { Tag, Typography } from 'antd';
import { LoadingOutlined, CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import type { TaskItem } from '../types';

const { Text } = Typography;

interface TaskTimelineProps {
    tasks: TaskItem[];
}

const TaskTimeline: React.FC<TaskTimelineProps> = ({ tasks }) => {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {tasks.map((task, index) => (
                <div key={index} style={{ display: 'flex', gap: 12 }}>
                    <div style={{ paddingTop: 4 }}>
                        {task.status === 'process' && <LoadingOutlined style={{ color: '#1677ff', fontSize: 16 }} />}
                        {task.status === 'finish' && <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />}
                        {task.status === 'error' && <ClockCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />}
                        {task.status === 'pending' && <ClockCircleOutlined style={{ color: '#d9d9d9', fontSize: 16 }} />}
                    </div>
                    <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                            <Text strong style={{ color: task.status === 'pending' ? '#999' : undefined }}>{task.title}</Text>
                            {task.duration !== undefined && (
                                <Tag variant="filled" style={{ margin: 0, fontSize: 11, color: '#666' }}>
                                    {(task.duration / 1000).toFixed(2)}s
                                </Tag>
                            )}
                        </div>
                        
                        {/* Description / Result Summary */}
                        {task.description && (
                             <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>{task.description}</div>
                        )}

                        {/* Thinking Logs (Collapsible or just small text) */}
                        {task.status === 'process' && task.logs && task.logs.length > 0 && (
                            <div style={{ 
                                background: '#f5f5f5', 
                                padding: '8px 12px', 
                                borderRadius: 6, 
                                fontSize: 12, 
                                color: '#666',
                                fontFamily: 'monospace',
                                maxHeight: 150,
                                overflowY: 'auto',
                                border: '1px solid #f0f0f0'
                            }}>
                                {task.logs.map((log, i) => (
                                    <div key={i}>{log}</div>
                                ))}
                                <div id={`log-end-${index}`} />
                            </div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
};

export default TaskTimeline;
