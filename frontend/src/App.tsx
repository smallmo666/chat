import React, { useState, useRef, useEffect } from 'react';
import { Layout, Input, Button, Card, Steps, Typography, List, Splitter, Tag, ConfigProvider, theme, Tree, Collapse, Table } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, LoadingOutlined, CheckCircleOutlined, SyncOutlined, ClockCircleOutlined, TableOutlined, SearchOutlined, ColumnHeightOutlined, BarChartOutlined, FileTextOutlined, CaretRightOutlined } from '@ant-design/icons';
import { Brain, Database, Activity } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';

const { Header, Content } = Layout;
const { TextArea } = Input;
const { Title, Text } = Typography;
const { DirectoryTree } = Tree;

interface Message {
  role: 'user' | 'agent';
  content?: string | React.ReactNode;
  thinking?: string;
}

interface TaskItem {
  id: string;
  title: string;
  status: 'pending' | 'process' | 'finish' | 'error';
  description?: React.ReactNode;
  duration?: number;
  logs?: string[];
}

const TaskTimeline: React.FC<{ tasks: TaskItem[] }> = ({ tasks }) => {
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
                                <Tag bordered={false} style={{ margin: 0, fontSize: 11, color: '#666' }}>
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

interface TableColumn {
    name: string;
    type: string;
    comment?: string;
}

interface TableSchema {
    name: string;
    comment?: string;
    columns: TableColumn[];
}

interface TreeDataNode {
    title: React.ReactNode;
    key: string;
    isLeaf?: boolean;
    children?: TreeDataNode[];
    icon?: React.ReactNode;
}

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  // const [thinkingContent, setThinkingContent] = useState(''); // Removed
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [tasks, setTasks] = useState<TaskItem[]>([
    { id: 'init', title: '等待输入...', status: 'pending' }
  ]);
  const [threadId, setThreadId] = useState<string>('');

  // Schema Browser State
  const [dbTables, setDbTables] = useState<TableSchema[]>([]);
  const [tableSearch, setTableSearch] = useState('');
  const [treeData, setTreeData] = useState<TreeDataNode[]>([]);
  const [checkedKeys, setCheckedKeys] = useState<React.Key[]>([]);
  const [autoExpandParent, setAutoExpandParent] = useState<boolean>(true);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  // const thinkingEndRef = useRef<HTMLDivElement>(null); // Removed

  useEffect(() => {
      // Generate Thread ID on mount
      const tid = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36);
      setThreadId(tid);

      // Fetch table list on mount
      fetch('http://localhost:8000/tables')
        .then(res => res.json())
        .then(data => {
            if (data.tables) {
                setDbTables(data.tables);
            }
        })
        .catch(err => console.error("Failed to fetch tables", err));
  }, []);

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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  // const scrollToThinkingBottom = () => {
  //   thinkingEndRef.current?.scrollIntoView({ behavior: "smooth" });
  // };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // useEffect(() => {
  //   scrollToThinkingBottom();
  // }, [thinkingContent]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMsg = inputValue;
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInputValue('');
    setIsLoading(true);
    // setThinkingContent('');
    
    // Add initial agent message placeholder
    setMessages(prev => [...prev, { role: 'agent', thinking: '', content: '' }]);

    // Only send top-level table names (not columns)
    const selectedTables = checkedKeys.filter(k => typeof k === 'string' && !k.includes('.'));
    
    // Reset steps (Initial placeholder, will be updated by 'plan' event)
    setTasks([
      { id: 'planning', title: '正在规划...', status: 'process', description: <Tag color="processing" icon={<LoadingOutlined />}>AI 思考中</Tag> },
    ]);
    setCurrentStep(0);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            message: userMsg,
            selected_tables: selectedTables.length > 0 ? selectedTables : undefined,
            thread_id: threadId
        }),
      });

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
            // Ensure loading state is cleared when stream ends
            setIsLoading(false);
            break;
        }

        buffer += decoder.decode(value, { stream: true });
        
        // Parse SSE events
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.split('\n')[0].replace('event: ', '').trim();
            const dataStr = line.split('\n')[1]?.replace('data: ', '').trim();
            
            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);

              if (eventType === 'thinking') {
                // Update thinking content of the last message
                setMessages(prev => {
                    const newMsgs = [...prev];
                    const lastMsg = newMsgs[newMsgs.length - 1];
                    if (lastMsg && lastMsg.role === 'agent') {
                        newMsgs[newMsgs.length - 1] = {
                            ...lastMsg,
                            thinking: (lastMsg.thinking || '') + data.content
                        };
                    }
                    return newMsgs;
                });
                
                // Also append to current task logs (but we might hide it from UI)
                // Keeping logic for now in case we want to re-enable
                // setTasks(prev => ...); // Removed to avoid clutter and perf issues since we show thinking in chat
              }
              else if (eventType === 'plan') {
                // Receive dynamic plan from backend
                const newTasks: TaskItem[] = data.content.map((step: any, index: number) => ({
                    id: step.node,
                    title: step.desc, // Use description as title
                    status: index === 0 ? 'process' : 'pending',
                    description: index === 0 ? <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag> : '等待中',
                    logs: []
                }));
                setTasks(newTasks);
                setCurrentStep(0);
              }
              else if (eventType === 'step') {
                updateStepStatus(data.node, data.status, data.details, data.duration);
              }
              else if (eventType === 'result') {
                // Update content of the last message (usually the one with thinking)
                setMessages(prev => {
                    const newMsgs = [...prev];
                    const lastMsg = newMsgs[newMsgs.length - 1];
                    // If last message is the one streaming thinking, update its content
                    // If content is empty string, replace it. If string, append? Usually replace for result.
                    if (lastMsg && lastMsg.role === 'agent') {
                         newMsgs[newMsgs.length - 1] = {
                            ...lastMsg,
                            content: data.content
                        };
                    }
                    return newMsgs;
                });
              }
              else if (eventType === 'analysis') {
                  // Render Markdown Analysis - Append as NEW message or Compound?
                  // Let's append as new message to keep bubbles clean
                  const markdownContent = (
                      <Card size="small" title={<span style={{display:'flex', alignItems:'center'}}><FileTextOutlined style={{marginRight:6}}/> 数据洞察</span>} style={{marginTop: 8, background: '#f6ffed', borderColor: '#b7eb8f'}}>
                          <ReactMarkdown>{data.content}</ReactMarkdown>
                      </Card>
                  );
                  setMessages(prev => [...prev, { role: 'agent', content: markdownContent }]);
              }
              else if (eventType === 'visualization') {
                  const vizData = data.content;
                  let vizContent = null;
                  
                  if (vizData.chart_type === 'table' && vizData.table_data) {
                      // Render Ant Design Table
                      const { columns, data: tableData } = vizData.table_data;
                      
                      // Auto-generate columns definition
                      const tableColumns = columns.map((col: string) => ({
                          title: col,
                          dataIndex: col,
                          key: col,
                          render: (text: any) => <span style={{fontSize: 13}}>{text}</span>
                      }));
                      
                      vizContent = (
                          <Card size="small" title={<span style={{display:'flex', alignItems:'center'}}><TableOutlined style={{marginRight:6}}/> 数据清单</span>} style={{marginTop: 8, overflow: 'hidden'}}>
                              <Table 
                                dataSource={tableData} 
                                columns={tableColumns} 
                                size="small" 
                                pagination={{ pageSize: 5, size: 'small' }}
                                scroll={{ x: 'max-content' }}
                                rowKey={(record, index) => index?.toString() || ''}
                              />
                          </Card>
                      );
                  } else {
                      // Render ECharts (Default)
                      const option = vizData.option || vizData;
                      
                      vizContent = (
                          <Card size="small" title={<span style={{display:'flex', alignItems:'center'}}><BarChartOutlined style={{marginRight:6}}/> 可视化图表</span>} style={{marginTop: 8}}>
                              <ReactECharts option={option} style={{height: 500, width: '100%'}} theme="macarons" />
                          </Card>
                      );
                  }
                  
                  if (vizContent) {
                      setMessages(prev => {
                          const newMsgs = [...prev];
                          const lastMsg = newMsgs[newMsgs.length - 1];
                          // If last message is an empty placeholder (no content, no thinking), replace it
                          // This happens when ExecuteSQL sends visualization without prior thinking
                          if (lastMsg && lastMsg.role === 'agent' && !lastMsg.content && !lastMsg.thinking) {
                              newMsgs[newMsgs.length - 1] = {
                                  ...lastMsg,
                                  content: vizContent
                              };
                          } else {
                              // Otherwise append as new message
                              newMsgs.push({ role: 'agent', content: vizContent });
                          }
                          return newMsgs;
                      });
                  }
                  
                  // Ensure loading state is cleared when visualization is received
                  setIsLoading(false);
              }
              else if (eventType === 'selected_tables') {
                 // Agent auto-selected tables, update UI checkboxes
                 if (Array.isArray(data.content)) {
                     setCheckedKeys(prev => data.content);
                     setExpandedKeys(prev => [...new Set([...prev, ...data.content])]);
                 }
              }
              else if (eventType === 'error') {
                 setMessages(prev => [...prev, { role: 'agent', content: `Error: ${data.content}` }]);
                 setIsLoading(false);
              }
            } catch (e) {
              console.error("Failed to parse SSE data", e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { role: 'agent', content: '抱歉，系统出现错误。' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const updateStepStatus = (node: string, status: string, details: string, duration?: number) => {
    setTasks(prev => {
      const newTasks = [...prev];
      
      // Find task by ID (Case sensitive match with backend node name)
      // Backend node names: "Planner", "Supervisor", "ClarifyIntent", "SelectTables", "GenerateDSL", "DSLtoSQL", "ExecuteSQL", "DataAnalysis", "Visualization", "TableQA"
      const taskIndex = newTasks.findIndex(t => t.id === node);
      
      if (taskIndex !== -1) {
          // Format details
          let desc: React.ReactNode = details || '完成';
          if (details && details.length > 50) {
            desc = <Tag color="blue" style={{whiteSpace: 'normal', wordBreak: 'break-all'}}>{details}</Tag>;
          }
          
          // Update current task status
          newTasks[taskIndex] = {
              ...newTasks[taskIndex],
              status: 'finish',
              description: desc,
              duration: duration
          };
          
          // Trigger next task if available
          if (taskIndex + 1 < newTasks.length) {
              // Only start next task if it's currently 'wait'
              if (newTasks[taskIndex + 1].status === 'pending') {
                  newTasks[taskIndex + 1].status = 'process';
                  newTasks[taskIndex + 1].description = <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag>;
                  // We don't rely on currentStep state anymore for rendering, just for logic if needed
                  setCurrentStep(taskIndex + 1);
              }
          }
      } else {
          console.warn(`Step event for unknown node: ${node}`);
      }
      return newTasks;
    });
  };
  
  // Removed filteredTables since we use treeData derived in useEffect
  
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
        },
      }}
    >
      <Layout style={{ height: '100vh', background: '#f0f2f5' }}>
        <Header style={{ 
          display: 'flex', 
          alignItems: 'center', 
          background: '#001529', 
          padding: '0 24px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          zIndex: 10
        }}>
          <Database style={{ color: '#1677ff', marginRight: 12 }} size={24} />
          <Title level={4} style={{ color: 'white', margin: 0, fontWeight: 600 }}>Demo</Title>
        </Header>
        
        <Content style={{ padding: '0', height: 'calc(100vh - 64px)' }}>
          <Splitter style={{ height: '100%', background: 'white', borderRadius: 0 }}>
              {/* Left Sidebar: Schema Browser */}
              <Splitter.Panel defaultSize="20%" min="15%" style={{borderRight: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column'}}>
                 <div style={{padding: '16px', borderBottom: '1px solid #f0f0f0', background: '#fafafa'}}>
                    <div style={{display: 'flex', alignItems: 'center', marginBottom: 12}}>
                        <TableOutlined style={{marginRight: 8}} />
                        <Text strong>数据库表 ({dbTables.length})</Text>
                    </div>
                    <Input 
                        placeholder="搜索表..." 
                        prefix={<SearchOutlined style={{color: '#bfbfbf'}} />} 
                        value={tableSearch}
                        onChange={e => setTableSearch(e.target.value)}
                        allowClear
                    />
                 </div>
                 <div style={{flex: 1, overflow: 'auto', padding: '0 8px'}}>
                    <DirectoryTree
                        checkable
                        multiple
                        treeData={treeData}
                        showIcon
                        style={{background: 'transparent'}}
                        height={800} // Virtual scroll
                        checkedKeys={checkedKeys}
                        onCheck={(checked) => {
                            // DirectoryTree onCheck returns {checked: [], halfChecked: []} or just [] depending on strict mode
                            // But for simple usage it returns array of keys
                            if (Array.isArray(checked)) {
                                setCheckedKeys(checked);
                            } else {
                                setCheckedKeys(checked.checked);
                            }
                        }}
                        expandedKeys={expandedKeys}
                        onExpand={(expanded) => setExpandedKeys(expanded)}
                        autoExpandParent={autoExpandParent}
                    />
                 </div>
              </Splitter.Panel>

              {/* Middle: Chat */}
              <Splitter.Panel defaultSize="60%" min="40%">
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                      
                      {/* Chat Area */}
                      <div style={{ flex: 1, padding: '16px 16px 0 16px', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                          <Card 
                              title={<span style={{display: 'flex', alignItems: 'center'}}><UserOutlined style={{marginRight: 8}}/> 对话交互</span>}
                              bordered={false}
                              style={{ height: '100%', display: 'flex', flexDirection: 'column', boxShadow: 'none', background: '#fafafa' }}
                              styles={{ body: { flex: 1, overflowY: 'auto', padding: '16px', background: 'white', borderRadius: '0 0 8px 8px' } }}
                          >
                              <List
                                  itemLayout="horizontal"
                                  dataSource={messages}
                                  split={false}
                                  renderItem={(item) => (
                                      <List.Item style={{ padding: '8px 0', border: 'none' }}>
                                          <div style={{ 
                                              width: '100%', 
                                              display: 'flex', 
                                              justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start' 
                                          }}>
                                              <div style={{ 
                                                  maxWidth: item.role === 'user' ? '80%' : '100%', 
                                                  padding: '10px 14px', 
                                                  borderRadius: item.role === 'user' ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                                                  background: item.role === 'user' ? '#1677ff' : '#f5f5f5',
                                                  color: item.role === 'user' ? 'white' : 'rgba(0,0,0,0.88)',
                                                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                                                  fontSize: '14px',
                                                  lineHeight: 1.6,
                                                  overflow: 'hidden' // Ensure content like charts doesn't overflow bubble
                                              }}>
                                                  {item.role === 'agent' && (
                                                      <div style={{display: 'flex', alignItems: 'center', marginBottom: 4, opacity: 0.7, fontSize: 12}}>
                                                      <RobotOutlined style={{ marginRight: 4 }} /> Agent
                                                      </div>
                                                  )}
                                                  
                                                  {/* Thinking Process */}
                                                  {item.role === 'agent' && item.thinking && (
                                                      <Collapse 
                                                          size="small"
                                                          ghost
                                                          expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ fontSize: 10, color: '#888' }} />}
                                                          items={[{ 
                                                              key: '1', 
                                                              label: <span style={{fontSize: 12, color: '#888'}}>思考过程</span>, 
                                                              children: <div style={{whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, color: '#666', background: '#eee', padding: 8, borderRadius: 4, maxHeight: 300, overflowY: 'auto'}}>{item.thinking}</div>
                                                          }]}
                                                          style={{ marginBottom: 8, background: 'rgba(0,0,0,0.02)', borderRadius: 4 }}
                                                      />
                                                  )}

                                                  {/* Result Content */}
                                                  {item.content && <div style={{whiteSpace: 'pre-wrap'}}>{item.content}</div>}
                                                  
                                                  {/* Loading State for empty content */}
                                                  {!item.content && !item.thinking && item.role === 'agent' && (
                                                       <SyncOutlined spin style={{color: '#1677ff'}} />
                                                  )}
                                              </div>
                                          </div>
                                      </List.Item>
                                  )}
                              />
                              <div ref={messagesEndRef} />
                          </Card>
                      </div>

                      {/* Input Area (Fixed at bottom) */}
                      <div style={{ padding: '0 16px 16px 16px', flexShrink: 0 }}>
                        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', background: 'white', padding: 12, borderRadius: 12, border: '1px solid #f0f0f0' }}>
                            <TextArea 
                                value={inputValue}
                                onChange={e => setInputValue(e.target.value)}
                                onPressEnter={(e) => {
                                    if (!e.shiftKey) {
                                        e.preventDefault();
                                        handleSendMessage();
                                    }
                                }}
                                placeholder="请输入您的查询，例如：查询所有年龄大于20的用户..." 
                                autoSize={{ minRows: 1, maxRows: 4 }}
                                style={{ borderRadius: 8, padding: '8px 12px', resize: 'none', border: 'none', boxShadow: 'none', background: '#f9f9f9' }}
                            />
                            <Button 
                                type="primary" 
                                size="large"
                                icon={isLoading ? <LoadingOutlined /> : <SendOutlined />} 
                                onClick={handleSendMessage}
                                disabled={isLoading}
                                style={{ height: 'auto', padding: '0 20px', borderRadius: 8 }}
                            >
                                发送
                            </Button>
                        </div>
                      </div>
                  </div>
              </Splitter.Panel>

              {/* Right: Execution Plan */}
              <Splitter.Panel defaultSize="20%" min="15%">
                  <div style={{ height: '100%', padding: 24, background: '#fafafa', borderLeft: '1px solid #f0f0f0', overflowY: 'auto' }}>
                      <Title level={5} style={{ marginBottom: 24, display: 'flex', alignItems: 'center' }}>
                        <Activity size={18} style={{ marginRight: 8, color: '#1677ff' }} />
                        执行计划追踪
                      </Title>
                      
                      <TaskTimeline tasks={tasks} />
                  </div>
              </Splitter.Panel>
          </Splitter>
        </Content>
      </Layout>
    </ConfigProvider>
  );
};

export default App;
