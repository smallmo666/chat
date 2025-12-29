import { Table, Button, Modal, Form, Input, Select, message, Tag, Transfer } from 'antd';
import { useState, useEffect } from 'react';
import { PlusOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

interface Project {
  id: number;
  name: str;
  data_source_id: number;
  scope_config: any;
}

interface DataSource {
  id: number;
  name: str;
}

const ProjectPage = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  // 获取项目和数据源列表
  const fetchData = async () => {
    setLoading(true);
    try {
      const [pRes, dRes] = await Promise.all([
        fetch('http://localhost:8000/api/projects'),
        fetch('http://localhost:8000/api/datasources')
      ]);
      setProjects(await pRes.json());
      setDataSources(await dRes.json());
    } catch (error) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async (values: any) => {
    // 基础实现：Scope 暂时为空或需要手动输入
    // 未来：添加 Transfer 组件以在选择数据源后选择表
    const payload = {
        name: values.name,
        data_source_id: values.data_source_id,
        scope_config: {} // 默认空范围表示所有表（或待定义的逻辑）
    };

    try {
      const res = await fetch('http://localhost:8000/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        message.success('项目创建成功');
        setIsModalOpen(false);
        form.resetFields();
        fetchData();
      } else {
        message.error('创建项目失败');
      }
    } catch (error) {
      message.error('创建项目时出错');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id' },
    { title: '项目名称', dataIndex: 'name', key: 'name' },
    { 
      title: '数据源', 
      key: 'ds',
      render: (_: any, record: Project) => {
        const ds = dataSources.find(d => d.id === record.data_source_id);
        return ds ? <Tag color="blue">{ds.name}</Tag> : record.data_source_id;
      }
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Project) => (
        <Button 
            type="primary" 
            icon={<PlayCircleOutlined />} 
            onClick={() => navigate(`/chat/${record.id}`)}
        >
            进入分析
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>项目管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)}>
          新增项目
        </Button>
      </div>
      <Table columns={columns} dataSource={projects} rowKey="id" loading={loading} />

      <Modal title="新增项目" open={isModalOpen} onOk={form.submit} onCancel={() => setIsModalOpen(false)}>
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item name="data_source_id" label="选择数据源" rules={[{ required: true, message: '请选择数据源' }]}>
            <Select 
                options={dataSources.map(d => ({ value: d.id, label: d.name }))} 
                placeholder="请选择数据源"
            />
          </Form.Item>
          {/* 未来：在此处添加基于所选数据源的表选择器 */}
        </Form>
      </Modal>
    </div>
  );
};

export default ProjectPage;
