import React, { useState, useEffect } from 'react';
import { Layout, ConfigProvider, theme, Typography, Splitter, Tag, Card, Table, Grid, Drawer, Button, List, Space, message, Tabs } from 'antd';
import { Activity } from 'lucide-react';
import { TableOutlined, BarChartOutlined, FileTextOutlined, LoadingOutlined, SyncOutlined, DatabaseOutlined, ProjectOutlined, CodeOutlined, SearchOutlined, BulbOutlined, CommentOutlined } from '@ant-design/icons';
const LazyECharts = React.lazy(() => import('echarts-for-react'));
import ReactMarkdown from 'react-markdown';
import { useParams, useNavigate } from 'react-router-dom';

import SchemaBrowser from '../components/SchemaBrowser';
import ChatWindow from '../components/ChatWindow';
import TaskTimeline from '../components/TaskTimeline';
import SessionList from '../components/SessionList';
import type { Message, TaskItem, ChatSession } from '../types';
import { SchemaProvider, useSchema } from '../context/SchemaContext';
import { fetchSessions, fetchSessionHistory, deleteSession, updateSessionTitle } from '../lib/api';

const { Content } = Layout;
const { useBreakpoint } = Grid;

import { ENDPOINTS, API_BASE_URL } from '../config';

const ChatPageContent: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const screens = useBreakpoint();
  // md: 768px. If screen is smaller than md, we consider it mobile/tablet.
  const isMobile = !screens.md; 
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [tasks, setTasks] = useState<TaskItem[]>([
    { id: 'init', title: '等待输入...', status: 'pending' }
  ]);
  const [threadId, setThreadId] = useState<string>('');
  
  // Session Management State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeLeftTab, setActiveLeftTab] = useState('schema');
  
  // Mobile Drawer States
  const [showSchema, setShowSchema] = useState(false);
  const [showTasks, setShowTasks] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  
  // State for latest data to export
  const [latestData, setLatestData] = useState<any[]>([]);

  // Splitter panel size state for collapsing
  const [leftPanelSize, setLeftPanelSize] = useState<string | number>('20%');

  // Use Context
  const { checkedKeys, setCheckedKeys } = useSchema();

  // Load Session List
  const loadSessions = async () => {
      if (!projectId) return;
      try {
          const list = await fetchSessions(parseInt(projectId));
          setSessions(list);
      } catch (error) {
          console.error("Failed to load sessions:", error);
      }
  };

  useEffect(() => {
      // Generate Thread ID on mount or retrieve from sessionStorage to persist across reloads
      // NOTE: For debugging loop issue, we force generate new ID if URL param changes or on hard reload
      let tid = sessionStorage.getItem('chat_thread_id');
      
      // If we have a project ID, try to load sessions
      if (projectId) {
          loadSessions();
      }

      if (!tid) {
          tid = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36);
          sessionStorage.setItem('chat_thread_id', tid);
      }
      setThreadId(tid);
      
      // Clear session storage on unmount to prevent stale state issues? No, we want persistence.
      // But we can add a way to clear it manually if needed.
  }, [projectId]);

  // Session Actions
  const handleSelectSession = async (sessionId: string) => {
      try {
          setIsLoading(true);
          setThreadId(sessionId);
          sessionStorage.setItem('chat_thread_id', sessionId);
          
          // Load history
          const history = await fetchSessionHistory(sessionId);
          
          // Transform history to messages
          const restoredMessages: Message[] = history.map((msg: any) => {
              // Handle complex content if necessary
              return {
                  role: msg.type === 'human' ? 'user' : 'agent',
                  content: msg.content
              };
          });
          
          setMessages(restoredMessages);
          
          // Reset tasks
          setTasks([{ id: 'init', title: '会话已恢复', status: 'finish' }]);
          
          if (isMobile) setShowSessions(false);
          
      } catch (error) {
          message.error('加载会话历史失败');
          console.error(error);
      } finally {
          setIsLoading(false);
      }
  };

  const handleNewChat = () => {
      const newId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36);
      setThreadId(newId);
      sessionStorage.setItem('chat_thread_id', newId);
      setMessages([]);
      setTasks([{ id: 'init', title: '等待输入...', status: 'pending' }]);
      if (isMobile) setShowSessions(false);
      
      // Optionally refresh list to ensure clean state, though new session isn't saved until first message
  };

  const handleDeleteSession = async (sessionId: string) => {
      try {
          await deleteSession(sessionId);
          message.success('会话已删除');
          loadSessions();
          if (threadId === sessionId) {
              handleNewChat();
          }
      } catch (error) {
          message.error('删除失败');
      }
  };

  const handleUpdateTitle = async (sessionId: string, title: string) => {
      try {
          await updateSessionTitle(sessionId, title);
          loadSessions();
      } catch (error) {
          message.error('重命名失败');
      }
  };

  const resetSession = () => {
      handleNewChat();
  };

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
      const token = localStorage.getItem('token');
      if (!token) {
        message.error('请先登录');
        navigate('/login');
        setIsLoading(false);
        return;
      }

      const response = await fetch(ENDPOINTS.CHAT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ 
            message: userMsg,
            selected_tables: selectedTables.length > 0 ? selectedTables : undefined,
            thread_id: threadId,
            project_id: projectId ? parseInt(projectId) : undefined
        }),
      });
      
      if (response.status === 401) {
          message.error('会话已过期，请重新登录');
          navigate('/login');
          setIsLoading(false);
          return;
      }

      // Refresh session list after first message sent (to show new session title)
      // Delay slightly to ensure backend created it
      setTimeout(loadSessions, 1000);

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let thinkingBuffer = '';
      let lastThinkingFlush = 0;
      let eventCounters: Record<string, number> = {};
      let lastHeartbeat = Date.now();

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
                thinkingBuffer += data.content;
                const now = performance.now();
                if (now - lastThinkingFlush > 50) {
                  const chunk = thinkingBuffer;
                  thinkingBuffer = '';
                  lastThinkingFlush = now;
                  setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      if (lastMsg && lastMsg.role === 'agent') {
                          newMsgs[newMsgs.length - 1] = {
                              ...lastMsg,
                              thinking: (lastMsg.thinking || '') + chunk
                          };
                      }
                      return newMsgs;
                  });
                }
              }
              eventCounters[eventType] = (eventCounters[eventType] || 0) + 1;
              const nowTs = Date.now();
              if (nowTs - lastHeartbeat > 5000) {
                  lastHeartbeat = nowTs;
                  console.log('SSE heartbeat', eventCounters);
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
                
                // Insert a new message for the plan
                setMessages(prev => [...prev, {
                    role: 'agent',
                    content: '', // Empty content as we use plan field
                    plan: newTasks
                }]);
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
                  // Set content to a simple text, ChatWindow will handle rendering via uiComponent field
                  setMessages(prev => {
                      const newMsgs = [...prev];
                      // Find if we have a message for Python analysis that can be merged, or create new
                      // Typically UI generation comes after python analysis or viz.
                      
                      // For simplicity, we just append or update the last agent message
                      // But we need to be careful not to overwrite 'thinking' or 'content' if they are streaming
                      
                      // Check if last message is agent and has empty content or is related
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      if (lastMsg && lastMsg.role === 'agent') {
                          // Merge into last message
                          newMsgs[newMsgs.length - 1] = {
                              ...lastMsg,
                              content: 'UI 组件已生成',
                              uiComponent: code
                          };
                      } else {
                          newMsgs.push({ 
                              role: 'agent', 
                              content: 'UI 组件已生成', 
                              uiComponent: code 
                          });
                      }
                      return newMsgs;
                  });
              }
              else if (eventType === 'python_images') {
                  const images = data.content; // Array of base64 strings
                  setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      if (lastMsg && lastMsg.role === 'agent') {
                          newMsgs[newMsgs.length - 1] = {
                              ...lastMsg,
                              images: images
                          };
                      } else {
                          // Should not happen usually, but fallback
                          newMsgs.push({ role: 'agent', content: '图表已生成', images: images });
                      }
                      return newMsgs;
                  });
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
              else if (eventType === 'data_download') {
                  const token = data.content;
                  const url = `${API_BASE_URL}/query/download?token=${encodeURIComponent(token)}`;
                  const card = (
                      <Card size="small" title="下载查询结果" style={{marginTop: 8}}>
                          <a href={url} target="_blank" rel="noreferrer">点击下载 CSV</a>
                      </Card>
                  );
                  setMessages(prev => [...prev, { role: 'agent', content: card }]);
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
                                size="middle" 
                                bordered
                                pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
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
                              <React.Suspense fallback={<div style={{height:500, display:'flex', alignItems:'center', justifyContent:'center', color:'#999'}}><LoadingOutlined style={{marginRight:8}} />加载图表...</div>}>
                                <LazyECharts option={option} style={{height: 500, width: '100%'}} theme="macarons" />
                              </React.Suspense>
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
    // Update the tasks state (though we might not display it in sidebar anymore)
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

    // Also update the plan in the message history
    setMessages(prev => {
        // Find the last message that has a plan
        // We need to clone deep enough
        const newMsgs = [...prev];
        // Reverse search for the plan message
        let planMsgIndex = -1;
        for (let i = newMsgs.length - 1; i >= 0; i--) {
            if (newMsgs[i].plan) {
                planMsgIndex = i;
                break;
            }
        }

        if (planMsgIndex !== -1) {
            const planMsg = { ...newMsgs[planMsgIndex] };
            const newPlan = [...(planMsg.plan || [])];
            const taskIndex = newPlan.findIndex(t => t.id === node);

            if (taskIndex !== -1) {
                let desc: React.ReactNode = details || '完成';
                if (details && details.length > 50) {
                    desc = <Tag color="blue" style={{whiteSpace: 'normal', wordBreak: 'break-all'}}>{details}</Tag>;
                }

                newPlan[taskIndex] = {
                    ...newPlan[taskIndex],
                    status: 'finish',
                    description: desc,
                    duration: duration
                };

                if (taskIndex + 1 < newPlan.length) {
                    if (newPlan[taskIndex + 1].status === 'pending') {
                        newPlan[taskIndex + 1].status = 'process';
                        newPlan[taskIndex + 1].description = <Tag color="processing" icon={<SyncOutlined spin />}>执行中...</Tag>;
                    }
                }
                
                planMsg.plan = newPlan;
                newMsgs[planMsgIndex] = planMsg;
            }
        }
        return newMsgs;
    });
  };

  const renderLeftPanel = () => {
      const items = [
          {
              key: 'schema',
              label: '数据库',
              icon: <DatabaseOutlined />,
              children: (
                  <SchemaBrowser 
                    onCollapse={() => setLeftPanelSize(0)} 
                    isCollapsed={leftPanelSize === 0 || leftPanelSize === '0%' || (typeof leftPanelSize === 'number' && leftPanelSize < 50)} 
                    onExpand={() => setLeftPanelSize('20%')}
                 />
              )
          },
          {
              key: 'sessions',
              label: '会话列表',
              icon: <CommentOutlined />,
              children: (
                  <SessionList 
                    sessions={sessions}
                    currentSessionId={threadId}
                    onSelectSession={handleSelectSession}
                    onNewChat={handleNewChat}
                    onDeleteSession={handleDeleteSession}
                    onUpdateTitle={handleUpdateTitle}
                  />
              )
          }
      ];

      return (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ padding: '0 16px', borderBottom: '1px solid #f0f0f0' }}>
                <Tabs 
                    activeKey={activeLeftTab} 
                    onChange={setActiveLeftTab}
                    items={items.map(i => ({ key: i.key, label: <span>{i.icon} {i.label}</span> }))}
                />
              </div>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                  {items.find(i => i.key === activeLeftTab)?.children}
              </div>
          </div>
      );
  };

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 12,
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif',
          colorBgContainer: '#ffffff',
          boxShadowSecondary: '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
        },
        components: {
          Card: {
            headerBg: 'transparent',
            boxShadowTertiary: '0 1px 2px 0 rgba(0, 0, 0, 0.03)',
          },
          Layout: {
            bodyBg: '#f0f2f5',
          },
          Splitter: {
            // Ant Design 5.x Splitter tokens might be different or not fully exposed yet in types
            // Removing specific color tokens to avoid type errors, using style overrides if needed
          }
        }
      }}
    >
      <Layout style={{ height: '100vh', background: '#f5f7fa', overflow: 'hidden' }}>
        <Content style={{ padding: isMobile ? '8px' : '0', margin: 0, height: '100%', overflow: 'hidden' }}>
          {isMobile ? (
             // Mobile Layout: Stack + Drawer
             <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
                 {/* Mobile Header Toolbar */}
                 <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                     <Button 
                         icon={<DatabaseOutlined />} 
                         onClick={() => setShowSchema(true)}
                         style={{ 
                             borderRadius: 20,
                             padding: '4px 12px',
                             height: 32,
                             fontSize: 13
                         }}
                     >
                         表结构
                     </Button>
                     <Button 
                         icon={<CommentOutlined />} 
                         onClick={() => setShowSessions(true)}
                         style={{ 
                             borderRadius: 20,
                             padding: '4px 12px',
                             height: 32,
                             fontSize: 13
                         }}
                     >
                         会话
                     </Button>
                     <Button 
                         icon={<ProjectOutlined />} 
                         onClick={() => setShowTasks(true)}
                         style={{ 
                             borderRadius: 20,
                             padding: '4px 12px',
                             height: 32,
                             fontSize: 13
                         }}
                     >
                         任务追踪
                     </Button>
                 </div>
                 
                 {/* Main Chat Area */}
                 <div style={{ flex: 1, background: 'white', borderRadius: 16, border: '1px solid rgba(0,0,0,0.06)', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
                    <ChatWindow 
                        messages={messages}
                        isLoading={isLoading}
                        onSendMessage={handleSendMessage}
                        latestData={latestData}
                        projectId={projectId}
                    />
                 </div>

                 {/* Drawers */}
                 <Drawer
                    title="数据库 Schema"
                    placement="left"
                    onClose={() => setShowSchema(false)}
                    open={showSchema}
                    styles={{ body: { padding: 0 }, wrapper: { width: '85%' } }}
                 >
                     <SchemaBrowser />
                 </Drawer>

                 <Drawer
                    title="会话列表"
                    placement="left"
                    onClose={() => setShowSessions(false)}
                    open={showSessions}
                    styles={{ body: { padding: 0 }, wrapper: { width: '85%' } }}
                 >
                     <SessionList 
                        sessions={sessions}
                        currentSessionId={threadId}
                        onSelectSession={handleSelectSession}
                        onNewChat={handleNewChat}
                        onDeleteSession={handleDeleteSession}
                        onUpdateTitle={handleUpdateTitle}
                      />
                 </Drawer>
                 
                 <Drawer
                    title="执行计划追踪"
                    placement="right"
                    onClose={() => setShowTasks(false)}
                    open={showTasks}
                    styles={{ body: { padding: 0 }, wrapper: { width: '85%' } }}
                 >
                     <TaskTimeline tasks={tasks} />
                 </Drawer>
             </div>
          ) : (
             // Desktop Layout: Splitter
             <Splitter 
                style={{ height: '100%', background: '#ffffff', borderRadius: 0, boxShadow: 'none', border: 'none' }}
                onResize={(sizes) => setLeftPanelSize(sizes[0])}
             >
              {/* Left Sidebar: Schema Browser / Session List */}
              <Splitter.Panel min="0%" max="40%" style={{borderRight: '1px solid rgba(0,0,0,0.06)'}} size={leftPanelSize}>
                 {renderLeftPanel()}
              </Splitter.Panel>

              {/* Middle: Chat */}
              <Splitter.Panel>
                  <ChatWindow 
                    messages={messages}
                    isLoading={isLoading}
                    onSendMessage={handleSendMessage}
                    latestData={latestData}
                    projectId={projectId}
                    onToggleSidebar={() => {
                        if (leftPanelSize === 0 || leftPanelSize === '0%' || (typeof leftPanelSize === 'number' && leftPanelSize < 50)) {
                            setLeftPanelSize('20%');
                        } else {
                            setLeftPanelSize(0);
                        }
                    }}
                    isLeftCollapsed={leftPanelSize === 0 || leftPanelSize === '0%' || (typeof leftPanelSize === 'number' && leftPanelSize < 50)}
                    onResetSession={resetSession}
                  />
              </Splitter.Panel>
          </Splitter>
          )}
        </Content>
      </Layout>
    </ConfigProvider>
  );
};

const ChatPage: React.FC = () => {
    const { projectId } = useParams<{ projectId: string }>();
    return (
        <SchemaProvider projectId={projectId}>
            <ChatPageContent />
        </SchemaProvider>
    );
};

export default ChatPage;
