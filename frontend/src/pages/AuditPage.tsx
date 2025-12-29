import { Table, Tag } from 'antd';
import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

interface AuditLog {
  id: number;
  session_id: str;
  user_query: str;
  status: str;
  duration_ms: number;
  created_at: str;
}

const AuditPage = () => {
  const [data, setData] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId');

  const fetchData = async () => {
    setLoading(true);
    try {
      let url = 'http://localhost:8000/api/audit/logs';
      if (projectId) {
          url += `?project_id=${projectId}`;
      }
      const res = await fetch(url);
      const json = await res.json();
      setData(json);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [projectId]);

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: '会话ID', dataIndex: 'session_id', key: 'session_id', ellipsis: true },
    { title: '查询内容', dataIndex: 'user_query', key: 'user_query', ellipsis: true },
    { 
        title: '状态', 
        dataIndex: 'status', 
        key: 'status',
        render: (status: str) => (
            <Tag color={status === 'success' ? 'green' : 'red'}>{status}</Tag>
        )
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
        render: (date: str) => new Date(date).toLocaleString()
    },
  ];

  return (
    <div>
      <h2>审计日志 {projectId && <Tag>项目 ID: {projectId}</Tag>}</h2>
      <Table columns={columns} dataSource={data} rowKey="id" loading={loading} />
    </div>
  );
};

export default AuditPage;
