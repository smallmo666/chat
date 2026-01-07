import React, { useState, useEffect } from 'react';
import { Input, Tree, Spin } from 'antd';
import { TableOutlined, SearchOutlined, ColumnHeightOutlined, MenuUnfoldOutlined, MenuFoldOutlined, DatabaseOutlined } from '@ant-design/icons';
import { Button, Tooltip } from 'antd';
import type { TreeDataNode, TableSchema } from '../types';
import { useSchema } from '../context/SchemaContext';

const { DirectoryTree } = Tree;

interface SchemaBrowserProps {
    onCollapse?: () => void;
    onExpand?: () => void;
    isCollapsed?: boolean;
}

const SchemaBrowser: React.FC<SchemaBrowserProps> = ({ onExpand, isCollapsed }) => {
    const { dbTables, checkedKeys, setCheckedKeys, loading } = useSchema();
    const [tableSearch, setTableSearch] = useState('');
    const [treeData, setTreeData] = useState<TreeDataNode[]>([]);
    const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
    const [autoExpandParent, setAutoExpandParent] = useState<boolean>(true);

    useEffect(() => {
        // Transform filtered tables to TreeData with Database Grouping
        const lowerSearch = tableSearch.toLowerCase();
        
        // 1. Filter Tables
        const filteredTables = dbTables.filter(t => {
            // Search in table name or comment
            return t.name.toLowerCase().includes(lowerSearch) || 
                   (t.comment && t.comment.toLowerCase().includes(lowerSearch));
        });

        // 2. Group by Database
        const dbGroups: Record<string, TableSchema[]> = {};
        
        filteredTables.forEach(t => {
            const parts = t.name.split('.');
            let dbName = 'Default';
            let tableName = t.name;
            
            // If name format is "db.table", group by db
            if (parts.length > 1) {
                dbName = parts[0];
                tableName = parts.slice(1).join('.'); // Handle cases with multiple dots if any
            }
            
            if (!dbGroups[dbName]) {
                dbGroups[dbName] = [];
            }
            
            // Store with adjusted name for display, but keep original for keys if needed
            // Actually, we should construct a new object to avoid mutating state
            dbGroups[dbName].push({
                ...t,
                name: tableName, // Display name (without db prefix)
                // We can store original name in a custom property if needed, but key handles it
            });
        });

        // 3. Build Tree Nodes
        const nodes: TreeDataNode[] = Object.entries(dbGroups).map(([dbName, tables]) => {
            return {
                title: (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', paddingRight: 8 }}>
                        <span style={{ fontWeight: 600, color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 8, fontSize: 13 }}>
                            {dbName}
                        </span>
                        <span style={{ color: '#999', fontSize: 11, flexShrink: 0, background: '#f5f5f5', padding: '0 5px', borderRadius: 8, minWidth: 18, textAlign: 'center' }}>
                            {tables.length}
                        </span>
                    </div>
                ),
                key: `db:${dbName}`,
                selectable: false,
                children: tables.map(t => {
                    const fullKey = dbName === 'Default' ? t.name : `${dbName}.${t.name}`;
                    return {
                        title: (
                            <div style={{ display: 'flex', alignItems: 'center', width: '100%', overflow: 'hidden' }}>
                                <Tooltip title={t.name} placement="topLeft" mouseEnterDelay={0.5}>
                                    <span style={{ fontWeight: 500, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0, maxWidth: '90%' }}>
                                        {t.name}
                                    </span>
                                </Tooltip>
                                {t.comment && (
                                    <span style={{ color: '#888', marginLeft: 6, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0, opacity: 0.7 }}>
                                        {t.comment}
                                    </span>
                                )}
                            </div>
                        ),
                        key: fullKey,
                        children: t.columns.map(col => ({
                            title: (
                                <div style={{ display: 'flex', alignItems: 'center', fontSize: 12, color: '#666', overflow: 'hidden', width: '100%' }}>
                                    <span style={{ color: '#1677ff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0, maxWidth: '60%' }}>
                                        {col.name}
                                    </span>
                                    <span style={{ color: '#999', margin: '0 4px', flexShrink: 0, fontSize: 11, transform: 'scale(0.9)' }}>{col.type}</span>
                                    {col.comment && (
                                        <span style={{ color: '#999', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0, fontSize: 11 }}>
                                            {col.comment}
                                        </span>
                                    )}
                                </div>
                            ),
                            key: `${fullKey}.${col.name}`,
                            isLeaf: true
                        }))
                    };
                })
            };
        });
          
        setTreeData(nodes);
        
        // Auto expand if searching
        if (tableSearch) {
             const allKeys: string[] = [];
             nodes.forEach(db => {
                 allKeys.push(db.key);
                 if (db.children) {
                     db.children.forEach(tbl => allKeys.push(tbl.key));
                 }
             });
             setExpandedKeys(allKeys);
        }
    }, [dbTables, tableSearch]);

    // Update expanded keys when search changes or tables are selected via agent
    useEffect(() => {
        if (checkedKeys.length > 0) {
             setExpandedKeys(prev => [...new Set([...prev, ...checkedKeys])]);
        }
    }, [checkedKeys]);

    if (isCollapsed) {
        return (
            <div style={{height: '100%', borderRight: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 0', background: '#fff'}}>
                <Tooltip title="展开侧边栏" placement="right">
                    <Button type="text" icon={<MenuUnfoldOutlined />} onClick={onExpand} />
                </Tooltip>
            </div>
        );
    }

    return (
        <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
            <div style={{
                padding: '8px 12px', 
                borderBottom: '1px solid #f0f0f0', 
                background: '#fff',
                display: 'flex',
                flexDirection: 'column',
                gap: 6
            }}>
                {/* Header Title Removed to save space */}
                <Input 
                    placeholder="搜索表名或注释..." 
                    prefix={<SearchOutlined style={{color: '#bfbfbf'}} />} 
                    value={tableSearch}
                    onChange={e => setTableSearch(e.target.value)}
                    allowClear
                    variant="filled"
                    style={{ borderRadius: 6, height: 32 }}
                    size="small"
                />
            </div>
            <div style={{flex: 1, overflow: 'hidden', padding: '8px 0', position: 'relative'}}>
                {loading ? (
                    <div style={{
                        display: 'flex', 
                        justifyContent: 'center', 
                        alignItems: 'center', 
                        height: '100%',
                        width: '100%',
                        flexDirection: 'column'
                    }}>
                        <Spin size="large" />
                        <div style={{marginTop: 10, color: '#999'}}>正在加载表结构...</div>
                    </div>
                ) : (
                    <div style={{height: '100%', overflow: 'auto'}}>
                    <DirectoryTree
                        checkable
                        multiple
                        draggable // Enable draggable
                        blockNode // Ensure nodes take full width
                        onDragStart={(info) => {
                            // Store dragged node info in dataTransfer
                            // We only want to drag table names or column names as text
                            info.event.dataTransfer.setData('text/plain', info.node.key as string);
                            // Also store a custom type to verify source
                            info.event.dataTransfer.setData('application/x-smallmo-schema', JSON.stringify({
                                key: info.node.key,
                                title: (info.node as any).title?.props?.children?.[0]?.props?.children || info.node.key
                            }));
                        }}
                        treeData={treeData}
                        showIcon={false}
                        style={{background: 'transparent', fontSize: 13}}
                        // height={800} // Virtual scroll removed for better auto-sizing
                        checkedKeys={checkedKeys}
                        onCheck={(checked) => {
                            if (Array.isArray(checked)) {
                                setCheckedKeys(checked);
                            } else {
                                setCheckedKeys(checked.checked);
                            }
                        }}
                        expandedKeys={expandedKeys}
                        onExpand={(expanded) => {
                            setExpandedKeys(expanded);
                            setAutoExpandParent(false);
                        }}
                        autoExpandParent={autoExpandParent}
                    />
                    </div>
                )}
            </div>
        </div>
    );
};

export default SchemaBrowser;
