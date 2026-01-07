import { Table, Button, Modal, Form, Input, InputNumber, Select, App, Popconfirm } from 'antd';
import { useState, useEffect } from 'react';
import { PlusOutlined, DeleteOutlined, ThunderboltOutlined, EditOutlined } from '@ant-design/icons';
import api from '../lib/api';

interface DataSource {
  id: number;
  name: string;
  type: string;
  host: string;
  port: number;
  user: string;
  dbname: string;
}

const DataSourcePage = () => {
  const [data, setData] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const { message } = App.useApp();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.post('/api/datasources/list');
      setData(res.data);
    } catch (error) {
      console.error('Fetch error:', error);
      message.error('加载数据源失败: 请检查后端服务是否正常启动');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateOrUpdate = async (values: any) => {
    try {
      const url = editingId 
        ? `/api/datasources/${editingId}`
        : '/api/datasources';
      
      if (editingId) {
        await api.put(url, values);
      } else {
        await api.post(url, values);
      }

      message.success(editingId ? '更新成功' : '创建成功');
      setIsModalOpen(false);
      setEditingId(null);
      form.resetFields();
      fetchData();
    } catch (error) {
      message.error('操作出错');
    }
  };

  const handleEdit = (record: DataSource) => {
      setEditingId(record.id);
      form.setFieldsValue(record);
      setIsModalOpen(true);
  };

  const handleTestConnection = async () => {
    try {
        const values = await form.validateFields(['type', 'host', 'port', 'user', 'password', 'dbname']);
        // Add dummy name for validation since backend requires it
        const payload = { ...values, name: 'test_connection' };
        await api.post('/api/datasources/test', payload);
        message.success('连接成功');
    } catch (error: any) {
        const errorMsg = error.response?.data?.detail || '测试连接时出错或表单验证失败';
        message.error(`连接失败: ${errorMsg}`);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/api/datasources/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (error) {
      message.error('删除数据源时出错');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 200 },
    { title: '类型', dataIndex: 'type', key: 'type', width: 120 },
    { title: '主机', dataIndex: 'host', key: 'host', width: 200 },
    { title: '端口', dataIndex: 'port', key: 'port', width: 100 },
    { 
      title: '数据库', 
      dataIndex: 'dbname', 
      key: 'dbname',
      width: 200,
      render: (text: string) => text || <span style={{ color: '#999', fontStyle: 'italic' }}>All Databases</span>
    },
    { title: '用户名', dataIndex: 'user', key: 'user', width: 150 },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: any, record: DataSource) => (
        <div style={{ display: 'flex', gap: 8 }}>
            <Button type="link" size="small" onClick={() => handleEdit(record)} style={{ padding: 0 }}>编辑</Button>
            <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
              <Button type="link" danger size="small" style={{ padding: 0 }}>删除</Button>
            </Popconfirm>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>数据源管理</h2>
        <Button type="primary" onClick={() => {
            setEditingId(null);
            form.resetFields();
            setIsModalOpen(true);
        }}>
          新增数据源
        </Button>
      </div>
      <Table 
        columns={columns} 
        dataSource={data} 
        rowKey="id" 
        loading={loading} 
        scroll={{ x: 1200 }} 
        pagination={{ pageSize: 10 }}
      />

      <Modal 
        title={editingId ? "编辑数据源" : "新增数据源"}
        open={isModalOpen} 
        onOk={form.submit} 
        onCancel={() => setIsModalOpen(false)}
        footer={[
            <Button key="test" icon={<ThunderboltOutlined />} onClick={handleTestConnection} style={{ float: 'left' }}>
                测试连接
            </Button>,
            <Button key="cancel" onClick={() => setIsModalOpen(false)}>
                取消
            </Button>,
            <Button key="submit" type="primary" onClick={form.submit}>
                确定
            </Button>,
        ]}
      >
        <Form form={form} onFinish={handleCreateOrUpdate} layout="vertical" initialValues={{ type: 'postgresql', port: 5432 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="请输入数据源名称" />
          </Form.Item>
          <Form.Item name="type" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select options={[{ value: 'postgresql', label: 'PostgreSQL' }, { value: 'mysql', label: 'MySQL' }]} />
          </Form.Item>
          <Form.Item name="host" label="主机" rules={[{ required: true, message: '请输入主机地址' }]}>
            <Input placeholder="localhost" />
          </Form.Item>
          <Form.Item name="port" label="端口" rules={[{ required: true, message: '请输入端口' }]}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="user" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="postgres" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password placeholder="******" />
          </Form.Item>
          <Form.Item name="dbname" label="数据库名" rules={[{ required: false, message: '请输入数据库名' }]}>
            <Input placeholder="如果不填则连接默认库并展示所有数据库" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DataSourcePage;
