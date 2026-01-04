import React from 'react';
import { Tag, Typography, Timeline } from 'antd';
import { LoadingOutlined, CheckCircleOutlined, ClockCircleOutlined, SyncOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { TaskItem } from '../types';

const { Text } = Typography;

interface TaskTimelineProps {
    tasks: TaskItem[];
}

const TaskTimeline: React.FC<TaskTimelineProps> = ({ tasks }) => {
    return (
        <div style={{ paddingLeft: 4 }}>
            <Timeline
                items={tasks.map((task, index) => {
                    let dot;
                    let color = 'gray';
                    
                    if (task.status === 'process') {
                        dot = <SyncOutlined spin style={{ fontSize: 16, color: '#1677ff' }} />;
                        color = 'blue';
                    } else if (task.status === 'finish') {
                        dot = <CheckCircleOutlined style={{ fontSize: 16, color: '#52c41a' }} />;
                        color = 'green';
                    } else if (task.status === 'error') {
                        dot = <CloseCircleOutlined style={{ fontSize: 16, color: '#ff4d4f' }} />;
                        color = 'red';
                    } else {
                        dot = <ClockCircleOutlined style={{ fontSize: 16, color: '#d9d9d9' }} />;
                        color = 'gray';
                    }

                    return {
                        color: color,
                        dot: dot,
                        children: (
                            <div style={{ paddingBottom: 16 }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                                    <Text strong style={{ 
                                        color: task.status === 'pending' ? '#999' : '#333',
                                        fontSize: 14
                                    }}>
                                        {task.title}
                                    </Text>
                                    {task.duration !== undefined && (
                                        <Tag bordered={false} style={{ margin: 0, fontSize: 11, color: '#888', background: '#f5f5f5' }}>
                                            {(task.duration / 1000).toFixed(2)}s
                                        </Tag>
                                    )}
                                </div>
                                
                                {/* Description / Result Summary */}
                                {task.description && (
                                     <div style={{ fontSize: 13, color: '#666', marginBottom: 6, lineHeight: 1.5 }}>
                                         {task.description}
                                     </div>
                                )}

                                {/* Thinking Logs */}
                                {task.status === 'process' && task.logs && task.logs.length > 0 && (
                                    <div style={{ 
                                        background: '#f9f9f9', 
                                        padding: '8px 12px', 
                                        borderRadius: 6, 
                                        fontSize: 12, 
                                        color: '#666',
                                        fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace',
                                        maxHeight: 150,
                                        overflowY: 'auto',
                                        border: '1px solid #f0f0f0',
                                        marginTop: 8
                                    }}>
                                        {task.logs.map((log, i) => (
                                            <div key={i} style={{ marginBottom: 2 }}>{log}</div>
                                        ))}
                                        <div id={`log-end-${index}`} />
                                    </div>
                                )}
                            </div>
                        )
                    };
                })}
            />
        </div>
    );
};

export default TaskTimeline;
