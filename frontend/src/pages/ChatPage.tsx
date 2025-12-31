import React, { useState, useEffect } from 'react';
import { Layout, ConfigProvider, theme, Typography, Splitter, Tag, Card, Table, Grid, Drawer, Button, List, Space } from 'antd';
import { Activity } from 'lucide-react';
import { TableOutlined, BarChartOutlined, FileTextOutlined, LoadingOutlined, SyncOutlined, DatabaseOutlined, ProjectOutlined, CodeOutlined, SearchOutlined, BulbOutlined, BgColorsOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import { useParams } from 'react-router-dom';

import SchemaBrowser from '../components/SchemaBrowser';
import ChatWindow from '../components/ChatWindow';
import TaskTimeline from '../components/TaskTimeline';
import type { Message, TaskItem } from '../types';
import { SchemaProvider, useSchema } from '../context/SchemaContext';

const { Content } = Layout;
const { Title } = Typography;
const { useBreakpoint } = Grid;

import { ENDPOINTS } from '../config';

const ChatPageContent: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const screens = useBreakpoint();
  // md: 768px. If screen is smaller than md, we consider it mobile/tablet.
  const isMobile = !screens.md; 
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [tasks, setTasks] = useState<TaskItem[]>([
    { id: 'init', title: '等待输入...', status: 'pending' }
  ]);
  const [threadId, setThreadId] = useState<string>('');
  
  // Mobile Drawer States
  const [showSchema, setShowSchema] = useState(false);
  const [showTasks, setShowTasks] = useState(false);
  
  // State for latest data to export
  const [latestData, setLatestData] = useState<any[]>([]);

  // Use Context
  const { checkedKeys, setCheckedKeys } = useSchema();

  useEffect(() => {
      // Generate Thread ID on mount
      const tid = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36);
      setThreadId(tid);
  }, []);

  const handleSendMessage = async (userMsg: string) => {
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);
    setLatestData([]); // Reset latest data on new query
    
    // Add initial agent message placeholder
    setMessages(prev => [...prev, { role: 'agent', thinking: '', content: '' }]);

    // Only send top-level table names (not columns)
    const selectedTables = checkedKeys.filter(k => typeof k === 'string' && !k.toString().includes('.'));
    
    // Reset steps (Initial placeholder, will be updated by 'plan' event)
    setTasks([
      { id: 'planning', title: '正在规划...', status: 'process', description: <Tag color="processing" icon={<LoadingOutlined />}>AI 思考中</Tag> },
    ]);

    try {
      const response = await fetch(ENDPOINTS.CHAT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            message: userMsg,
            selected_tables: selectedTables.length > 0 ? selectedTables : undefined,
            thread_id: threadId,
            project_id: projectId ? parseInt(projectId) : undefined
        }),
      });

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
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
              }
              else if (eventType === 'plan') {
                const newTasks: TaskItem[] = data.content.map((step: any, index: number) => ({
                    id: step.node,
                    title: step.desc,
                    status: index === 0 ? 'process' : 'pending',
                    description: index === 0 ? <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag> : '等待中',
                    logs: []
                }));
                setTasks(newTasks);
              }
              else if (eventType === 'step') {
                updateStepStatus(data.node, data.status, data.details, data.duration);
              }
              else if (eventType === 'interrupt') {
                setMessages(prev => [...prev, { 
                    role: 'agent', 
                    content: data.content, // The SQL string
                    interrupt: true 
                }]);
                setIsLoading(false);
              }
              else if (eventType === 'detective_insight') {
                  const { hypotheses, depth } = data;
                  const insightContent = (
                      <Card 
                          size="small" 
                          title={<Space><SearchOutlined style={{color: '#1677ff'}} /> 侦探思考 (模式: {depth === 'deep' ? '深度' : '快速'})</Space>} 
                          style={{marginTop: 8, background: '#f0f5ff', borderColor: '#adc6ff'}}
                      >
                          <List
                              size="small"
                              dataSource={hypotheses}
                              renderItem={(item: any) => (
                                  <List.Item>
                                      <Typography.Text>🕵️‍♂️ {item}</Typography.Text>
                                  </List.Item>
                              )}
                          />
                      </Card>
                  );
                  setMessages(prev => [...prev, { role: 'agent', content: insightContent, hypotheses, analysisDepth: depth }]);
              }
              else if (eventType === 'insight_mined') {
                  const insights = data.content;
                  const insightCard = (
                      <Card 
                          size="small" 
                          title={<Space><BulbOutlined style={{color: '#faad14'}} /> 主动洞察发现</Space>} 
                          style={{marginTop: 8, background: '#fffbe6', borderColor: '#ffe58f'}}
                      >
                           <List
                              size="small"
                              dataSource={insights}
                              renderItem={(item: any) => (
                                  <List.Item>
                                      <Typography.Text>💡 {item}</Typography.Text>
                                  </List.Item>
                              )}
                          />
                      </Card>
                  );
                  setMessages(prev => [...prev, { role: 'agent', content: insightCard, insights }]);
              }
              else if (eventType === 'ui_generated') {
                  const code = data.content;
                  const uiCard = (
                      <Card 
                          size="small" 
                          title={<Space><BgColorsOutlined style={{color: '#722ed1'}} /> 生成式 UI (React Code)</Space>} 
                          style={{marginTop: 8, background: '#f9f0ff', borderColor: '#d3adf7'}}
                      >
                          <Typography.Paragraph type="secondary" style={{fontSize: 12}}>
                              * 这是一个自动生成的 React 组件代码，可直接用于前端渲染。
                          </Typography.Paragraph>
                          <ReactMarkdown 
                            components={{
                                code({node, inline, className, children, ...props}: any) {
                                    return !inline ? (
                                        <div style={{background: '#282c34', color: '#abb2bf', padding: '12px', borderRadius: '4px', overflowX: 'auto', fontFamily: 'monospace'}}>
                                            <pre style={{margin: 0}}><code>{children}</code></pre>
                                        </div>
                                    ) : (
                                        <code className={className} {...props}>{children}</code>
                                    )
                                }
                            }}
                        >
                            {`\`\`\`jsx\n${code}\n\`\`\``}
                        </ReactMarkdown>
                      </Card>
                  );
                  setMessages(prev => [...prev, { role: 'agent', content: uiCard, uiComponent: code }]);
              }
              else if (eventType === 'code_generated') {
                const codeContent = (
                    <Card size="small" title={<span style={{display:'flex', alignItems:'center'}}><CodeOutlined style={{marginRight:6}}/> 生成的 Python 代码</span>} style={{marginTop: 8, background: '#f9f9f9', borderColor: '#d9d9d9'}}>
                        <ReactMarkdown 
                            components={{
                                code({node, inline, className, children, ...props}: any) {
                                    return !inline ? (
                                        <div style={{background: '#282c34', color: '#abb2bf', padding: '12px', borderRadius: '4px', overflowX: 'auto', fontFamily: 'monospace'}}>
                                            <pre style={{margin: 0}}><code>{children}</code></pre>
                                        </div>
                                    ) : (
                                        <code className={className} {...props}>{children}</code>
                                    )
                                }
                            }}
                        >
                            {`\`\`\`python\n${data.content}\n\`\`\``}
                        </ReactMarkdown>
                    </Card>
                );
                setMessages(prev => [...prev, { role: 'agent', content: codeContent }]);
              }
              else if (eventType === 'result') {
                setMessages(prev => {
                    const newMsgs = [...prev];
                    const lastMsg = newMsgs[newMsgs.length - 1];
                    if (lastMsg && lastMsg.role === 'agent') {
                         newMsgs[newMsgs.length - 1] = {
                            ...lastMsg,
                            content: data.content
                        };
                    }
                    return newMsgs;
                });
              }
              else if (eventType === 'data_export') {
                  setLatestData(data.content);
                  setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      if (lastMsg && lastMsg.role === 'agent') {
                          newMsgs[newMsgs.length - 1] = {
                              ...lastMsg,
                              data: data.content
                          };
                      }
                      return newMsgs;
                  });
              }
              else if (eventType === 'analysis') {
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
                      const { columns, data: tableData } = vizData.table_data;
                      
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
                                rowKey={(record, index) => {
                                    if (record.id !== undefined && record.id !== null) return record.id;
                                    if (record.key !== undefined) return record.key;
                                    if (record.code !== undefined) return record.code;
                                    return index?.toString() || `row-${Math.random()}`;
                                }}
                              />
                          </Card>
                      );
                  } else {
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
                          if (lastMsg && lastMsg.role === 'agent' && !lastMsg.content && !lastMsg.thinking) {
                              newMsgs[newMsgs.length - 1] = {
                                  ...lastMsg,
                                  content: vizContent,
                                  vizOption: vizData.option || vizData // Store raw option
                              };
                          } else {
                              newMsgs.push({ 
                                  role: 'agent', 
                                  content: vizContent,
                                  vizOption: vizData.option || vizData
                              });
                          }
                          return newMsgs;
                      });
                  }
                  setIsLoading(false);
              }
              else if (eventType === 'selected_tables') {
                 if (Array.isArray(data.content)) {
                     setCheckedKeys(data.content);
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

  const updateStepStatus = (node: string, _status: string, details: string, duration?: number) => {
    setTasks(prev => {
      const newTasks = [...prev];
      const taskIndex = newTasks.findIndex(t => t.id === node);
      
      if (taskIndex !== -1) {
          let desc: React.ReactNode = details || '完成';
          if (details && details.length > 50) {
            desc = <Tag color="blue" style={{whiteSpace: 'normal', wordBreak: 'break-all'}}>{details}</Tag>;
          }
          
          newTasks[taskIndex] = {
              ...newTasks[taskIndex],
              status: 'finish',
              description: desc,
              duration: duration
          };
          
          if (taskIndex + 1 < newTasks.length) {
              if (newTasks[taskIndex + 1].status === 'pending') {
                  newTasks[taskIndex + 1].status = 'process';
                  newTasks[taskIndex + 1].description = <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag>;
              }
          }
      }
      return newTasks;
    });
  };

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
      <Layout style={{ height: '100%', background: 'transparent' }}>
        <Content style={{ padding: isMobile ? '8px' : '16px', height: '100%' }}>
          {isMobile ? (
             // Mobile Layout: Stack + Drawer
             <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
                 {/* Mobile Header Toolbar */}
                 <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                     <Button icon={<DatabaseOutlined />} onClick={() => setShowSchema(true)}>表结构</Button>
                     <Button icon={<ProjectOutlined />} onClick={() => setShowTasks(true)}>任务追踪</Button>
                 </div>
                 
                 {/* Main Chat Area */}
                 <div style={{ flex: 1, background: 'white', borderRadius: 12, border: '1px solid #f0f0f0', overflow: 'hidden' }}>
                    <ChatWindow 
                        messages={messages}
                        isLoading={isLoading}
                        onSendMessage={handleSendMessage}
                        latestData={latestData}
                    />
                 </div>

                 {/* Drawers */}
                 <Drawer
                    title="数据库 Schema"
                    placement="left"
                    onClose={() => setShowSchema(false)}
                    open={showSchema}
                    width="85%"
                 >
                     <SchemaBrowser />
                 </Drawer>
                 
                 <Drawer
                    title="执行计划追踪"
                    placement="right"
                    onClose={() => setShowTasks(false)}
                    open={showTasks}
                    width="85%"
                 >
                     <TaskTimeline tasks={tasks} />
                 </Drawer>
             </div>
          ) : (
             // Desktop Layout: Splitter
             <Splitter style={{ height: '100%', background: 'white', borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', border: '1px solid #f0f0f0' }}>
              {/* Left Sidebar: Schema Browser */}
              <Splitter.Panel defaultSize="20%" min="15%" style={{borderRight: '1px solid #f0f0f0'}}>
                 <SchemaBrowser />
              </Splitter.Panel>

              {/* Middle: Chat */}
              <Splitter.Panel defaultSize="60%" min="40%">
                  <ChatWindow 
                    messages={messages}
                    isLoading={isLoading}
                    onSendMessage={handleSendMessage}
                    latestData={latestData}
                  />
              </Splitter.Panel>

              {/* Right: Execution Plan */}
              <Splitter.Panel defaultSize="20%" min="15%">
                  <div style={{ height: '100%', padding: 0, background: '#fafafa', borderLeft: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ padding: '16px 24px', borderBottom: '1px solid #f0f0f0', background: '#fff' }}>
                        <Title level={5} style={{ margin: 0, display: 'flex', alignItems: 'center', fontSize: 15 }}>
                            <Activity size={16} style={{ marginRight: 8, color: '#1677ff' }} />
                            执行计划追踪
                        </Title>
                      </div>
                      
                      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
                        <TaskTimeline tasks={tasks} />
                      </div>
                  </div>
              </Splitter.Panel>
          </Splitter>
          )}
        </Content>
      </Layout>
    </ConfigProvider>
  );
};

const ChatPage: React.FC = () => {
    return (
        <SchemaProvider>
            <ChatPageContent />
        </SchemaProvider>
    );
};

export default ChatPage;
