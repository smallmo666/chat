import React, { useState, useMemo } from 'react';
import { Button, Typography, Popconfirm, Input, Tooltip, theme, Empty } from 'antd';
import { 
    PlusOutlined, DeleteOutlined, EditOutlined, MessageOutlined, 
    CalendarOutlined 
} from '@ant-design/icons';
import type { ChatSession } from '../types';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import isToday from 'dayjs/plugin/isToday';
import isYesterday from 'dayjs/plugin/isYesterday';

dayjs.extend(relativeTime);
dayjs.extend(isToday);
dayjs.extend(isYesterday);

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
    const { token } = theme.useToken();
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState('');
    const [hoveredId, setHoveredId] = useState<string | null>(null);

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

    // Group sessions by time
    const groupedSessions = useMemo(() => {
        const groups: { label: string; items: ChatSession[] }[] = [
            { label: '今天', items: [] },
            { label: '昨天', items: [] },
            { label: '7天内', items: [] },
            { label: '更早', items: [] },
        ];

        sessions.forEach(session => {
            const date = dayjs(session.updated_at);
            if (date.isToday()) {
                groups[0].items.push(session);
            } else if (date.isYesterday()) {
                groups[1].items.push(session);
            } else if (date.isAfter(dayjs().subtract(7, 'day'))) {
                groups[2].items.push(session);
            } else {
                groups[3].items.push(session);
            }
        });

        return groups.filter(g => g.items.length > 0);
    }, [sessions]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
            <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid #f0f0f0' }}>
                <Button 
                    type="primary" 
                    icon={<PlusOutlined />} 
                    block 
                    onClick={onNewChat}
                    style={{ 
                        height: 40, 
                        borderRadius: 8, 
                        background: `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryActive} 100%)`,
                        border: 'none',
                        boxShadow: '0 4px 10px rgba(22, 119, 255, 0.2)',
                        fontWeight: 500
                    }}
                >
                    开启新会话
                </Button>
            </div>
            
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 0' }}>
                {sessions.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史会话" style={{marginTop: 40}} />
                ) : (
                    groupedSessions.map(group => (
                        <div key={group.label} style={{ marginBottom: 20 }}>
                            <div style={{ 
                                padding: '0 20px 8px', 
                                color: '#999', 
                                fontSize: 12, 
                                fontWeight: 600,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                            }}>
                                <CalendarOutlined style={{ fontSize: 10 }} /> {group.label}
                            </div>
                            {group.items.map(item => (
                                <div
                                    key={item.id}
                                    style={{
                                        position: 'relative',
                                        padding: '10px 16px 10px 20px',
                                        cursor: 'pointer',
                                        backgroundColor: currentSessionId === item.id ? '#e6f4ff' : 'transparent',
                                        transition: 'all 0.2s',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 12,
                                        margin: '0 8px',
                                        borderRadius: 8
                                    }}
                                    onClick={() => onSelectSession(item.id)}
                                    onMouseEnter={() => setHoveredId(item.id)}
                                    onMouseLeave={() => setHoveredId(null)}
                                    className="session-item"
                                >
                                    {/* Active Indicator */}
                                    {currentSessionId === item.id && (
                                        <div style={{
                                            position: 'absolute',
                                            left: 0,
                                            top: '50%',
                                            transform: 'translateY(-50%)',
                                            width: 3,
                                            height: 20,
                                            background: token.colorPrimary,
                                            borderRadius: '0 2px 2px 0'
                                        }} />
                                    )}

                                    <MessageOutlined style={{ 
                                        fontSize: 16, 
                                        color: currentSessionId === item.id ? token.colorPrimary : '#bfbfbf',
                                        flexShrink: 0
                                    }} />

                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        {editingId === item.id ? (
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
                                            <Text 
                                                ellipsis 
                                                style={{ 
                                                    display: 'block', 
                                                    color: currentSessionId === item.id ? token.colorText : '#595959',
                                                    fontWeight: currentSessionId === item.id ? 500 : 400
                                                }}
                                            >
                                                {item.title}
                                            </Text>
                                        )}
                                        {!editingId && (
                                            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 2 }}>
                                                {dayjs(item.updated_at).fromNow()}
                                            </Text>
                                        )}
                                    </div>

                                    {/* Actions (Show on hover or active) */}
                                    {(hoveredId === item.id || currentSessionId === item.id) && !editingId && (
                                        <div style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
                                            <Tooltip title="重命名">
                                                <Button 
                                                    type="text" 
                                                    size="small" 
                                                    icon={<EditOutlined />} 
                                                    onClick={(e) => handleEditStart(item, e)}
                                                    style={{ color: '#8c8c8c' }}
                                                />
                                            </Tooltip>
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
                                                <Button 
                                                    type="text" 
                                                    size="small" 
                                                    icon={<DeleteOutlined />} 
                                                    style={{ color: '#ff4d4f' }}
                                                />
                                            </Popconfirm>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    ))
                )}
            </div>
            <style>{`
                .session-item:hover {
                    background: #f5f5f5;
                }
            `}</style>
        </div>
    );
};

export default SessionList;
