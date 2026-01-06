import { Table, Tag, Drawer, Descriptions, Typography, Timeline, Card, Button } from 'antd';
import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ClockCircleOutlined, CheckCircleOutlined, CodeOutlined, ProjectOutlined } from '@ant-design/icons';
import api from '../lib/api';

const { Title, Text, Paragraph } = Typography;

interface AuditLog {
  id: number;
  session_id: string;
  user_query: string;
  status: string;
  execution_time: number;
  created_at: string;
  plan: any[];
  executed_sql: string;
  result_summary: string;
  error_message: string;
  duration_ms: number;
}

const AuditPage = () => {
  const [data, setData] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId');
  
  // Drawer state
  const [visible, setVisible] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.post('/api/audit/logs/list', {
          project_id: projectId ? parseInt(projectId) : undefined
      });
      setData(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      console.error(error);
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [projectId]);

  const showDrawer = (record: AuditLog) => {
      setSelectedLog(record);
      setVisible(true);
  };

  const onClose = () => {
      setVisible(false);
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: '会话ID', dataIndex: 'session_id', key: 'session_id', ellipsis: true },
    { title: '查询内容', dataIndex: 'user_query', key: 'user_query', ellipsis: true },
    { 
        title: '状态', 
        dataIndex: 'status', 
        key: 'status',
        render: (status: string) => (
            <Tag color={status === 'success' ? 'green' : 'red'}>
                {status?.toUpperCase() || 'UNKNOWN'}
            </Tag>
        ),
    },
    { 
        title: '耗时', 
        dataIndex: 'duration_ms', 
        key: 'duration_ms',
        render: (ms: number) => `${ms}ms`
    },
    {
        title: '时间',
        dataIndex: 'created_at',
        key: 'created_at',
        render: (date: string) => new Date(date).toLocaleString()
    },
    {
        title: '操作',
        key: 'action',
        render: (_: any, record: AuditLog) => (
            <Button type="link" size="small" onClick={() => showDrawer(record)}>
                查看详情
            </Button>
        ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Title level={4} style={{ margin: 0 }}>
              <ProjectOutlined /> 审计日志
              {projectId && <Tag style={{ marginLeft: 8 }} color="blue">Project ID: {projectId}</Tag>}
          </Title>
          <Button onClick={fetchData} loading={loading}>刷新</Button>
      </div>
      
      <Table 
        columns={columns} 
        dataSource={data} 
        rowKey="id" 
        loading={loading} 
        size="middle"
        pagination={{ pageSize: 10 }}
      />
      
      <Drawer
        title="日志详情"
        placement="right"
        size="large"
        onClose={onClose}
        open={visible}
      >
          {selectedLog && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  <Descriptions bordered column={1} size="small">
                      <Descriptions.Item label="Session ID">{selectedLog.session_id}</Descriptions.Item>
                      <Descriptions.Item label="Time">{new Date(selectedLog.created_at).toLocaleString()}</Descriptions.Item>
                      <Descriptions.Item label="Status">
                          <Tag color={selectedLog.status === 'success' ? 'green' : 'red'}>{selectedLog.status}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Duration">{selectedLog.duration_ms} ms</Descriptions.Item>
                      <Descriptions.Item label="Result">{selectedLog.result_summary || '-'}</Descriptions.Item>
                  </Descriptions>
                  
                  <Card size="small" title="用户查询" style={{ background: '#f9f9f9' }}>
                      <Text style={{ fontSize: 16 }}>{selectedLog.user_query}</Text>
                  </Card>
                  
                  {selectedLog.executed_sql && (
                      <Card size="small" title={<><CodeOutlined /> 执行 SQL</>} style={{ borderColor: '#91caff' }}>
                          <Paragraph copyable style={{ margin: 0, fontFamily: 'monospace', color: '#0050b3' }}>
                              {selectedLog.executed_sql}
                          </Paragraph>
                      </Card>
                  )}
                  
                  {selectedLog.error_message && (
                      <Card size="small" title="错误信息" style={{ borderColor: '#ffccc7', background: '#fff1f0' }}>
                          <Text type="danger">{selectedLog.error_message}</Text>
                      </Card>
                  )}
                  
                  {selectedLog.plan && Array.isArray(selectedLog.plan) && (
                      <Card size="small" title="执行计划">
                          <Timeline
                              items={selectedLog.plan.map((step: any) => ({
                                  color: step.status === 'finish' || step.status === 'completed' ? 'green' : 'gray',
                                  children: (
                                      <>
                                          <Text strong>{step.node}</Text>
                                          <br/>
                                          <Text type="secondary">{step.desc}</Text>
                                      </>
                                  ),
                                  icon: step.status === 'finish' || step.status === 'completed' ? <CheckCircleOutlined /> : <ClockCircleOutlined />
                              }))}
                          />
                      </Card>
                  )}
              </div>
          )}
      </Drawer>
    </div>
  );
};

export default AuditPage;
