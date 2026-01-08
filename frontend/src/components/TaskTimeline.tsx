import React from 'react';
import { Tag, Typography, Steps, theme } from 'antd';
import { CheckCircleFilled, LoadingOutlined, CloseCircleFilled, ClockCircleFilled } from '@ant-design/icons';
import type { TaskItem } from '../chatTypes';

const { Text } = Typography;

interface TaskTimelineProps {
    tasks: TaskItem[];
}

const TaskTimeline: React.FC<TaskTimelineProps> = ({ tasks }) => {
    const { token } = theme.useToken();

    const renderIcon = (status: string, size: number = 14) => {
        const style = { fontSize: size, color: '' };
        if (status === 'process') {
            style.color = token.colorPrimary;
            return <LoadingOutlined style={style} />;
        }
        if (status === 'finish') {
            style.color = token.colorSuccess;
            return <CheckCircleFilled style={style} />;
        }
        if (status === 'error') {
            style.color = token.colorError;
            return <CloseCircleFilled style={style} />;
        }
        style.color = token.colorTextQuaternary;
        return <ClockCircleFilled style={style} />;
    };

    const renderDuration = (duration?: number) => {
        if (!duration) return null;
        return (
            <Tag bordered={false} style={{ margin: 0, fontSize: 11, color: token.colorTextSecondary }}>
                {(duration / 1000).toFixed(2)}s
            </Tag>
        );
    };

    return (
        <div style={{ padding: '8px 4px' }}>
            <Steps
                direction="vertical"
                size="small"
                current={tasks.findIndex(t => t.status === 'process')}
                items={tasks.map((task) => ({
                    title: (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                            <Text style={{ 
                                fontSize: 14, 
                                fontWeight: task.status === 'process' ? 500 : 400,
                                color: task.status === 'pending' ? token.colorTextQuaternary : token.colorText
                            }}>
                                {task.title}
                            </Text>
                            {renderDuration(task.duration)}
                        </div>
                    ),
                    description: (
                        <div style={{ marginTop: 4 }}>
                            {task.description && (
                                <div style={{ 
                                    fontSize: 13, 
                                    color: token.colorTextSecondary,
                                    lineHeight: 1.5,
                                    background: task.status === 'process' ? token.colorFillAlter : 'transparent',
                                    padding: task.status === 'process' ? '4px 8px' : 0,
                                    borderRadius: 4,
                                    marginBottom: 8,
                                    display: 'inline-block'
                                }}>
                                    {task.description}
                                </div>
                            )}
                            
                            {/* Subtasks Rendering */}
                            {task.subtasks && task.subtasks.length > 0 && (
                                <div style={{ 
                                    display: 'flex', 
                                    flexDirection: 'column', 
                                    gap: 6, 
                                    marginTop: 4,
                                    paddingLeft: 4,
                                    borderLeft: `2px solid ${token.colorFillAlter}`
                                }}>
                                    {task.subtasks.map((sub, idx) => (
                                        <div key={idx} style={{ 
                                            display: 'flex', alignItems: 'flex-start', gap: 8,
                                            padding: '2px 0 2px 8px',
                                            fontSize: 12,
                                            color: token.colorTextSecondary
                                        }}>
                                            <div style={{ marginTop: 2 }}>{renderIcon(sub.status, 12)}</div>
                                            <div style={{ flex: 1 }}>
                                                <span style={{ fontWeight: 500, marginRight: 6 }}>{sub.title}</span>
                                                <span style={{ color: token.colorTextTertiary }}>{sub.description}</span>
                                            </div>
                                            {/* Subtask duration if we had it, currently 0 */}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ),
                    status: task.status as any,
                    icon: renderIcon(task.status)
                }))}
            />
        </div>
    );
};

export default TaskTimeline;
