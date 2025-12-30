import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, App, Space, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import api from '../lib/api';

interface LLMProvider {
  id: number;
  name: string;
  provider: string;
  model_name: string;
  api_base?: string;
}

const SettingsPage: React.FC = () => {
  const [llms, setLlms] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [editingId, setEditingId] = useState<number | null>(null);
  const { message } = App.useApp();

  const fetchLLMs = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/llms');
      setLlms(res.data);
    } catch (error) {
      message.error('Failed to load LLM providers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLLMs();
  }, []);

  const handleAdd = () => {
    setEditingId(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const handleEdit = (record: LLMProvider) => {
    setEditingId(record.id);
    form.setFieldsValue(record);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/api/llms/${id}`);
      message.success('Deleted successfully');
      fetchLLMs();
    } catch (error) {
      message.error('Failed to delete');
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingId) {
        await api.put(`/api/llms/${editingId}`, values);
        message.success('Updated successfully');
      } else {
        await api.post('/api/llms', values);
        message.success('Created successfully');
      }
      setIsModalOpen(false);
      fetchLLMs();
    } catch (error) {
      // Form validation error or API error
      console.error(error);
    }
  };

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { 
        title: 'Provider', 
        dataIndex: 'provider', 
        key: 'provider',
        render: (text: string) => <Tag color="blue">{text}</Tag>
    },
    { title: 'Model Name', dataIndex: 'model_name', key: 'model_name' },
    { title: 'API Base', dataIndex: 'api_base', key: 'api_base' },
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: LLMProvider) => (
        <Space size="middle">
          <Button icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          <Button icon={<DeleteOutlined />} danger onClick={() => handleDelete(record.id)} />
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>LLM Model Management</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          Add Provider
        </Button>
      </div>
      
      <Table 
        columns={columns} 
        dataSource={llms} 
        rowKey="id" 
        loading={loading} 
      />

      <Modal 
        title={editingId ? "Edit LLM Provider" : "Add LLM Provider"} 
        open={isModalOpen} 
        onOk={handleOk} 
        onCancel={() => setIsModalOpen(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Production GPT-4" />
          </Form.Item>
          <Form.Item name="provider" label="Provider" initialValue="openai">
            <Select>
                <Select.Option value="openai">OpenAI</Select.Option>
                <Select.Option value="azure">Azure OpenAI</Select.Option>
                <Select.Option value="ollama">Ollama</Select.Option>
                <Select.Option value="anthropic">Anthropic</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="model_name" label="Model Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. gpt-4o, llama3" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="Leave empty to keep unchanged" />
          </Form.Item>
          <Form.Item name="api_base" label="API Base URL (Optional)">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SettingsPage;
