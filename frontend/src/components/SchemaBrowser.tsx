import React, { useState, useEffect } from 'react';
import { Input, Tree } from 'antd';
import { TableOutlined, SearchOutlined, ColumnHeightOutlined } from '@ant-design/icons';
import type { TreeDataNode } from '../types';
import { useSchema } from '../context/SchemaContext';

const { DirectoryTree } = Tree;

const SchemaBrowser: React.FC = () => {
    const { dbTables, checkedKeys, setCheckedKeys } = useSchema();
    const [tableSearch, setTableSearch] = useState('');
    const [treeData, setTreeData] = useState<TreeDataNode[]>([]);
    const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
    const [autoExpandParent, setAutoExpandParent] = useState<boolean>(true);

    useEffect(() => {
        // Transform filtered tables to TreeData
        const lowerSearch = tableSearch.toLowerCase();
        
        const nodes: TreeDataNode[] = dbTables
          .filter(t => {
              // Search in table name or comment
              return t.name.toLowerCase().includes(lowerSearch) || 
                     (t.comment && t.comment.toLowerCase().includes(lowerSearch));
          })
          .map(t => {
              return {
                  title: (
                      <span style={{fontSize: 14}}>
                          <span style={{fontWeight: 500}}>{t.name}</span>
                          {t.comment && <span style={{color: '#888', marginLeft: 6}}>({t.comment})</span>}
                      </span>
                  ),
                  key: t.name,
                  icon: <TableOutlined />,
                  children: t.columns.map(col => ({
                      title: (
                          <span style={{fontSize: 13, color: '#555'}}>
                              <span style={{color: '#1677ff'}}>{col.name}</span>
                              <span style={{color: '#999', margin: '0 4px'}}>{col.type}</span>
                              {col.comment && <span style={{color: '#666'}}>- {col.comment}</span>}
                          </span>
                      ),
                      key: `${t.name}.${col.name}`,
                      isLeaf: true,
                      icon: <ColumnHeightOutlined style={{fontSize: 11}} />
                  }))
              };
          });
          
        setTreeData(nodes);
    }, [dbTables, tableSearch]);

    // Update expanded keys when search changes or tables are selected via agent
    useEffect(() => {
        if (checkedKeys.length > 0) {
             setExpandedKeys(prev => [...new Set([...prev, ...checkedKeys])]);
        }
    }, [checkedKeys]);

    return (
        <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
            <div style={{
                padding: '16px 24px', 
                borderBottom: '1px solid #f0f0f0', 
                background: '#fff',
                display: 'flex',
                flexDirection: 'column',
                gap: 12
            }}>
                <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
                    <div style={{display: 'flex', alignItems: 'center', fontWeight: 600, fontSize: 15, color: '#1f1f1f'}}>
                        <TableOutlined style={{marginRight: 8, color: '#1677ff'}} />
                        数据表清单
                        <span style={{
                            marginLeft: 8, 
                            fontSize: 12, 
                            background: '#f0f0f0', 
                            padding: '2px 8px', 
                            borderRadius: 10, 
                            color: '#666',
                            fontWeight: 'normal'
                        }}>{dbTables.length}</span>
                    </div>
                </div>
                <Input 
                    placeholder="搜索表名或注释..." 
                    prefix={<SearchOutlined style={{color: '#bfbfbf'}} />} 
                    value={tableSearch}
                    onChange={e => setTableSearch(e.target.value)}
                    allowClear
                    variant="filled"
                    style={{ borderRadius: 8 }}
                />
            </div>
            <div style={{flex: 1, overflow: 'auto', padding: '12px 0'}}>
                <DirectoryTree
                    checkable
                    multiple
                    treeData={treeData}
                    showIcon
                    style={{background: 'transparent', fontSize: 13}}
                    height={800} // Virtual scroll
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
                    icon={(props: any) => {
                        if (props.isLeaf) return <ColumnHeightOutlined style={{fontSize: 11, color: '#8c8c8c'}} />;
                        return <TableOutlined style={{color: '#1677ff'}} />;
                    }}
                />
            </div>
        </div>
    );
};

export default SchemaBrowser;
