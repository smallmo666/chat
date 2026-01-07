import React, { useState } from 'react';
import { List, Button, Typography, Popconfirm, Input, Tooltip } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, MessageOutlined } from '@ant-design/icons';
import type { ChatSession } from '../types';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const { Text } = Typography;

interface SessionListProps {
    sessions: ChatSession[];
    currentSessionId: string | null;
    onSelectSession: (sessionId: string) => void;
    onNewChat: () => void;
    onDeleteSession: (sessionId: string) => void;
    onUpdateTitle: (sessionId: string, newTitle: string) => void;
}

const SessionList: React.FC<SessionListProps> = ({
    sessions,
    currentSessionId,
    onSelectSession,
    onNewChat,
    onDeleteSession,
    onUpdateTitle
}) => {
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState('');

    const handleEditStart = (session: ChatSession, e: React.MouseEvent) => {
        e.stopPropagation();
        setEditingId(session.id);
        setEditTitle(session.title);
    };

    const handleEditSave = (sessionId: string) => {
        if (editTitle.trim()) {
            onUpdateTitle(sessionId, editTitle);
        }
        setEditingId(null);
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
                <Button 
                    type="primary" 
                    icon={<PlusOutlined />} 
                    block 
                    onClick={onNewChat}
                >
                    新建会话
                </Button>
            </div>
            
            <div style={{ flex: 1, overflowY: 'auto' }}>
                <List
                    itemLayout="horizontal"
                    dataSource={sessions}
                    renderItem={(item) => (
                        <List.Item
                            key={item.id}
                            style={{
                                padding: '12px 16px',
                                cursor: 'pointer',
                                backgroundColor: currentSessionId === item.id ? '#e6f7ff' : 'transparent',
                                borderRight: currentSessionId === item.id ? '3px solid #1890ff' : 'none',
                                transition: 'all 0.3s'
                            }}
                            onClick={() => onSelectSession(item.id)}
                            actions={[
                                editingId !== item.id && (
                                    <Tooltip title="重命名">
                                        <EditOutlined 
                                            key="edit" 
                                            onClick={(e) => handleEditStart(item, e)} 
                                            style={{ color: '#8c8c8c' }}
                                        />
                                    </Tooltip>
                                ),
                                editingId !== item.id && (
                                    <Popconfirm
                                        title="确定删除此会话吗？"
                                        onConfirm={(e) => {
                                            e?.stopPropagation();
                                            onDeleteSession(item.id);
                                        }}
                                        onCancel={(e) => e?.stopPropagation()}
                                        okText="删除"
                                        cancelText="取消"
                                    >
                                        <DeleteOutlined 
                                            key="delete" 
                                            onClick={(e) => e.stopPropagation()} 
                                            style={{ color: '#ff4d4f' }}
                                        />
                                    </Popconfirm>
                                )
                            ].filter(Boolean) as React.ReactNode[]}
                        >
                            <List.Item.Meta
                                avatar={<MessageOutlined style={{ fontSize: '18px', color: '#1890ff', marginTop: '4px' }} />}
                                title={
                                    editingId === item.id ? (
                                        <Input
                                            value={editTitle}
                                            onChange={(e) => setEditTitle(e.target.value)}
                                            onPressEnter={() => handleEditSave(item.id)}
                                            onBlur={() => handleEditSave(item.id)}
                                            autoFocus
                                            onClick={(e) => e.stopPropagation()}
                                            size="small"
                                        />
                                    ) : (
                                        <Text ellipsis={{ tooltip: item.title }} style={{ maxWidth: 160, display: 'block' }}>
                                            {item.title}
                                        </Text>
                                    )
                                }
                                description={
                                    <Text type="secondary" style={{ fontSize: '12px' }}>
                                        {dayjs(item.updated_at).format('YYYY-MM-DD HH:mm:ss')}
                                    </Text>
                                }
                            />
                        </List.Item>
                    )}
                />
            </div>
        </div>
    );
};

export default SessionList;
