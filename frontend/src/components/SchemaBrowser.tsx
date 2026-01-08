import React, { useState, useEffect, useMemo } from 'react';
import { Input, Spin, Empty, Tag, Collapse, Typography, Tooltip, theme } from 'antd';
import { 
    SearchOutlined, TableOutlined, DatabaseOutlined, 
    MenuUnfoldOutlined, KeyOutlined 
} from '@ant-design/icons';
import { Button } from 'antd';
import { useSchema } from '../context/SchemaContext';

const { Text } = Typography;

interface SchemaBrowserProps {
    onCollapse?: () => void;
    onExpand?: () => void;
    isCollapsed?: boolean;
}

const getTypeColor = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes('int') || t.includes('id')) return 'blue';
    if (t.includes('char') || t.includes('text') || t.includes('string')) return 'green';
    if (t.includes('date') || t.includes('time') || t.includes('year')) return 'orange';
    if (t.includes('float') || t.includes('double') || t.includes('decimal') || t.includes('numeric')) return 'cyan';
    if (t.includes('bool')) return 'purple';
    return 'default';
};

const SchemaBrowser: React.FC<SchemaBrowserProps> = ({ onExpand, isCollapsed }) => {
    const { token } = theme.useToken();
    const { dbTables, loading } = useSchema();
    const [tableSearch, setTableSearch] = useState('');
    const [activeDbKeys, setActiveDbKeys] = useState<string[]>([]);
    
    // Group tables by Database
    const groupedTables = useMemo(() => {
        const lowerSearch = tableSearch.toLowerCase();
        const filtered = dbTables.filter(t => 
            t.name.toLowerCase().includes(lowerSearch) || 
            (t.comment && t.comment.toLowerCase().includes(lowerSearch))
        );

        const groups: Record<string, any[]> = {};
        filtered.forEach(t => {
            const parts = t.name.split('.');
            let dbName = 'Default';
            let tableName = t.name;
            if (parts.length > 1) {
                dbName = parts[0];
                tableName = parts.slice(1).join('.');
            }
            if (!groups[dbName]) groups[dbName] = [];
            groups[dbName].push({ ...t, displayName: tableName });
        });
        return groups;
    }, [dbTables, tableSearch]);

    // Update activeDbKeys when groupedTables changes (e.g. search or load)
    useEffect(() => {
        const allDbs = Object.keys(groupedTables);
        // Only expand if there is a search query
        if (allDbs.length > 0 && tableSearch) {
            setActiveDbKeys(allDbs);
        }
    }, [groupedTables, tableSearch]);

    const handleDragStart = (e: React.DragEvent, text: string) => {
        e.dataTransfer.setData('text/plain', text);
        e.dataTransfer.effectAllowed = 'copy';
    };

    if (isCollapsed) {
        return (
            <div style={{height: '100%', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px 0', background: 'var(--bg-container)'}}>
                <Tooltip title="展开数据库" placement="right">
                    <Button type="text" icon={<MenuUnfoldOutlined />} onClick={onExpand} size="large" />
                </Tooltip>
            </div>
        );
    }

    return (
        <div style={{display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-container)'}}>
            {/* Search Header */}
            <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid var(--border-color)' }}>
                <Input 
                    placeholder="搜索表名、字段..." 
                    prefix={<SearchOutlined style={{color: 'var(--text-tertiary)'}} />} 
                    value={tableSearch}
                    onChange={e => setTableSearch(e.target.value)}
                    allowClear
                    className="glass-input"
                    style={{ borderRadius: 8, background: 'var(--bg-color)', border: 'none' }}
                />
            </div>

            {/* Content Area */}
            <div style={{flex: 1, overflowY: 'auto', padding: '12px'}}>
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 40, flexDirection: 'column', alignItems: 'center', color: 'var(--text-tertiary)' }}>
                        <Spin />
                        <span style={{marginTop: 12, fontSize: 13}}>加载元数据...</span>
                    </div>
                ) : Object.keys(groupedTables).length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未找到相关表" style={{marginTop: 40, color: 'var(--text-tertiary)'}} />
                ) : (
                    <Collapse
                        ghost
                        activeKey={activeDbKeys}
                        onChange={(keys) => setActiveDbKeys(typeof keys === 'string' ? [keys] : keys as string[])}
                        expandIconPosition="end"
                        items={Object.entries(groupedTables).map(([dbName, tables]) => ({
                            key: dbName,
                            label: (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
                                    <DatabaseOutlined style={{ color: 'var(--text-secondary)', flexShrink: 0 }} /> 
                                    <Text 
                                        strong 
                                        ellipsis={{ tooltip: true }}
                                        style={{ fontSize: 13, textTransform: 'uppercase', color: 'var(--text-secondary)', flex: 1, minWidth: 0 }}
                                    >
                                        {dbName}
                                    </Text>
                                    <Tag bordered={false} style={{margin:0, fontSize: 10, lineHeight: '16px', flexShrink: 0, borderRadius: 10}}>{tables.length}</Tag>
                                </div>
                            ),
                            children: (
                                <Collapse 
                                    ghost 
                                    size="small"
                                    expandIconPosition="end"
                                    style={{ marginLeft: -12, marginRight: -12 }}
                                    items={tables.map((table: any) => ({
                                        key: table.name,
                                        label: (
                                            <div 
                                                draggable 
                                                onDragStart={(e) => handleDragStart(e, table.name)}
                                                style={{ display: 'flex', alignItems: 'center', width: '100%', overflow: 'hidden' }}
                                            >
                                                <TableOutlined style={{ marginRight: 8, color: token.colorPrimary }} />
                                                <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                                                    <Text strong style={{ fontSize: 13, color: 'var(--text-primary)' }} ellipsis>{table.displayName || table.name}</Text>
                                                    {table.comment && <Text type="secondary" style={{ fontSize: 11, color: 'var(--text-tertiary)' }} ellipsis>{table.comment}</Text>}
                                                </div>
                                            </div>
                                        ),
                                        children: (
                                            <div style={{ padding: '0 4px' }}>
                                                {table.columns.map((col: any) => (
                                                    <div 
                                                        key={col.name}
                                                        draggable
                                                        onDragStart={(e) => handleDragStart(e, col.name)}
                                                        style={{ 
                                                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                                            padding: '6px 10px', borderRadius: 6, cursor: 'grab',
                                                            background: 'var(--bg-color)', marginBottom: 4, border: '1px solid transparent',
                                                            transition: 'all 0.2s'
                                                        }}
                                                        className="column-item"
                                                    >
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
                                                            {(col.name === 'id' || col.primary_key) ? (
                                                                <KeyOutlined style={{ fontSize: 10, color: '#faad14' }} />
                                                            ) : (
                                                                <div style={{width: 10}} />
                                                            )}
                                                            <Text style={{ fontSize: 12, color: 'var(--text-primary)' }} ellipsis>{col.name}</Text>
                                                        </div>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                                                            <Tag bordered={false} color={getTypeColor(col.type)} style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 6px', borderRadius: 4 }}>
                                                                {col.type.toLowerCase()}
                                                            </Tag>
                                                        </div>
                                                    </div>
                                                ))}
                                                <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-tertiary)', textAlign: 'center', opacity: 0.6 }}>
                                                    按住拖拽字段到输入框
                                                </div>
                                            </div>
                                        )
                                    }))}
                                />
                            )
                        }))}
                    />
                )}
            </div>
            <style>{`
                .column-item:hover {
                    background: var(--primary-bg) !important;
                    border-color: ${token.colorPrimary}40 !important;
                }
                .ant-collapse-header {
                    align-items: center !important;
                    padding: 8px 0 !important;
                }
                .ant-collapse-content-box {
                    padding-bottom: 0 !important;
                }
            `}</style>
        </div>
    );
};

export default SchemaBrowser;
