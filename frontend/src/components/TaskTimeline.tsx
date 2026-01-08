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

    return (
        <div style={{ padding: '8px 4px' }}>
            <Steps
                direction="vertical"
                size="small"
                current={tasks.findIndex(t => t.status === 'process')}
                items={tasks.map((task, index) => {
                    let status: 'wait' | 'process' | 'finish' | 'error' = 'wait';
                    let icon;

                    if (task.status === 'process') {
                        status = 'process';
                        icon = <LoadingOutlined style={{ color: token.colorPrimary }} />;
                    } else if (task.status === 'finish') {
                        status = 'finish';
                        icon = <CheckCircleFilled style={{ color: token.colorSuccess }} />;
                    } else if (task.status === 'error') {
                        status = 'error';
                        icon = <CloseCircleFilled style={{ color: token.colorError }} />;
                    } else {
                        status = 'wait';
                        icon = <ClockCircleFilled style={{ color: token.colorTextQuaternary }} />;
                    }

                    return {
                        title: (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                <Text style={{ 
                                    fontSize: 14, 
                                    fontWeight: task.status === 'process' ? 500 : 400,
                                    color: task.status === 'pending' ? token.colorTextQuaternary : token.colorText
                                }}>
                                    {task.title}
                                </Text>
                                {task.duration !== undefined && (
                                    <Tag bordered={false} style={{ margin: 0, fontSize: 11, color: token.colorTextSecondary }}>
                                        {(task.duration / 1000).toFixed(2)}s
                                    </Tag>
                                )}
                            </div>
                        ),
                        description: task.description ? (
                            <div style={{ 
                                marginTop: 4, 
                                fontSize: 13, 
                                color: token.colorTextSecondary,
                                lineHeight: 1.5,
                                background: task.status === 'process' ? token.colorFillAlter : 'transparent',
                                padding: task.status === 'process' ? '4px 8px' : 0,
                                borderRadius: 4
                            }}>
                                {task.description}
                            </div>
                        ) : null,
                        status: status,
                        icon: icon
                    };
                })}
            />
        </div>
    );
};

export default TaskTimeline;
