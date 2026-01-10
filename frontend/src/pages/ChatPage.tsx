import React, { useState, useEffect } from 'react';
import { Layout, ConfigProvider, theme, Splitter, Grid, Drawer, Button, message, Tabs } from 'antd';
import { DatabaseOutlined, ProjectOutlined, CommentOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';

import SchemaBrowser from '../components/SchemaBrowser';
import ChatWindow from '../components/ChatWindow';
import TaskTimeline from '../components/TaskTimeline';
import SessionList from '../components/SessionList';
import type { Message, ChatSession } from '../chatTypes';
import { SchemaProvider, useSchema } from '../context/SchemaContext';
import { fetchSessions, fetchSessionHistory, deleteSession, updateSessionTitle, fetchProject } from '../lib/api';
import { useChatStream } from '../hooks/useChatStream';

const { Content } = Layout;
const { useBreakpoint } = Grid;

const ChatPageContent: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const screens = useBreakpoint();
  const isMobile = !screens.md; 
  
  const [threadId, setThreadId] = useState<string>('');
  
  // Session Management State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeLeftTab, setActiveLeftTab] = useState('schema');
  
  // Project Info
  const [projectName, setProjectName] = useState<string>('');
  
  // Mobile Drawer States
  const [showSchema, setShowSchema] = useState(false);
  const [showTasks, setShowTasks] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  
  // Splitter panel size state
  const [leftPanelSize, setLeftPanelSize] = useState<string | number>('20%');

  // Use Context
  const { checkedKeys } = useSchema();

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

  // Use Custom Hook for Chat Stream
  const { 
      messages, setMessages, 
      isLoading, setIsLoading,
      tasks, setTasks,
      sendMessage, 
      latestData 
  } = useChatStream({
      projectId,
      threadId,
      onSessionCreated: loadSessions
  });

  useEffect(() => {
      let tid = sessionStorage.getItem('chat_thread_id');
      
      if (projectId) {
          loadSessions();
          fetchProject(parseInt(projectId)).then(proj => {
              setProjectName(proj.name);
          }).catch(err => console.error("Failed to load project:", err));
      }

      if (!tid) {
          tid = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36);
          sessionStorage.setItem('chat_thread_id', tid);
      }
      setThreadId(tid);
  }, [projectId]);

  // Session Actions
  const handleSelectSession = async (sessionId: string) => {
      try {
          setIsLoading(true);
          setThreadId(sessionId);
          sessionStorage.setItem('chat_thread_id', sessionId);
          
          const history = await fetchSessionHistory(sessionId);
          
          const restoredMessages: Message[] = history.map((msg: any) => {
              return {
                  role: msg.type === 'human' ? 'user' : 'agent',
                  content: msg.content
              };
          });
          
          setMessages(restoredMessages);
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

  // Memoized Send Message Handler to prevent unnecessary re-renders of ChatWindow -> MessageBubble
  const handleSendMessage = React.useCallback((msg: string, cmd?: string, sql?: string, tables?: string[]) => {
      const isClarify = cmd === "clarify";
      const selected = isClarify ? (tables || []) : (tables || checkedKeys);
      sendMessage(msg, selected, cmd, sql);
  }, [sendMessage, checkedKeys]);

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
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-container)' }}>
              <div style={{ padding: '0 16px', borderBottom: '1px solid var(--border-color)' }}>
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
            bodyBg: 'var(--bg-color)',
          },
          Splitter: {
             // Ant Design 5.x Splitter styling
          }
        }
      }}
    >
      <Layout style={{ height: '100vh', background: 'var(--bg-color)', overflow: 'hidden' }}>
        <Content style={{ padding: isMobile ? '8px' : '0', margin: 0, height: '100%', overflow: 'hidden' }}>
          {isMobile ? (
             <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
                 {/* Mobile Header Toolbar */}
                 <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                     <Button 
                         icon={<DatabaseOutlined />} 
                         onClick={() => setShowSchema(true)}
                         style={{ borderRadius: 20, padding: '4px 12px', height: 32, fontSize: 13 }}
                     >
                         表结构
                     </Button>
                     <Button 
                         icon={<CommentOutlined />} 
                         onClick={() => setShowSessions(true)}
                         style={{ borderRadius: 20, padding: '4px 12px', height: 32, fontSize: 13 }}
                     >
                         会话
                     </Button>
                     <Button 
                         icon={<ProjectOutlined />} 
                         onClick={() => setShowTasks(true)}
                         style={{ borderRadius: 20, padding: '4px 12px', height: 32, fontSize: 13 }}
                     >
                         任务追踪
                     </Button>
                 </div>
                 
                 {/* Main Chat Area */}
                 <div style={{ flex: 1, background: 'var(--bg-container)', borderRadius: 16, border: '1px solid var(--border-color)', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
                    <ChatWindow 
                        messages={messages}
                        isLoading={isLoading}
                        onSendMessage={handleSendMessage}
                        latestData={latestData}
                        projectId={projectId}
                        projectName={projectName}
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
             <Splitter 
                style={{ height: '100%', background: 'transparent', borderRadius: 0, boxShadow: 'none', border: 'none' }}
                onResize={(sizes) => setLeftPanelSize(sizes[0])}
             >
              <Splitter.Panel min="0%" max="40%" style={{borderRight: '1px solid rgba(0,0,0,0.06)'}} size={leftPanelSize}>
                 {renderLeftPanel()}
              </Splitter.Panel>

              <Splitter.Panel>
                  <div style={{ height: '100%', background: 'linear-gradient(180deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0.8) 100%)' }}>
                    <ChatWindow 
                        messages={messages}
                        isLoading={isLoading}
                        onSendMessage={handleSendMessage}
                        latestData={latestData}
                        projectId={projectId}
                        projectName={projectName}
                        onToggleSidebar={() => {
                            if (leftPanelSize === 0 || leftPanelSize === '0%' || (typeof leftPanelSize === 'number' && leftPanelSize < 50)) {
                                setLeftPanelSize('20%');
                            } else {
                                setLeftPanelSize(0);
                            }
                        }}
                        isLeftCollapsed={leftPanelSize === 0 || leftPanelSize === '0%' || (typeof leftPanelSize === 'number' && leftPanelSize < 50)}
                        onResetSession={handleNewChat}
                    />
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
    const { projectId } = useParams<{ projectId: string }>();
    return (
        <SchemaProvider projectId={projectId}>
            <ChatPageContent />
        </SchemaProvider>
    );
};

export default ChatPage;
