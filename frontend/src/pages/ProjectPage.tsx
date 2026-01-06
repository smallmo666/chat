import React, { useEffect, useState } from 'react';
import { Card, Button, Typography, Space, Modal, Form, Input, Select, App, Empty, Tag, Row, Col } from 'antd';
import { PlusOutlined, ProjectOutlined, DatabaseOutlined, RightOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';

const { Title, Text } = Typography;
const { Option } = Select;

interface Project {
  id: number;
  name: string;
  data_source_id: number;
  scope_config: any;
}

interface DataSource {
  id: number;
  name: string;
}

const ProjectPage: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  const fetchData = async () => {
    setLoading(true);
    try {
        const [projRes, dsRes] = await Promise.all([
            api.post('/api/projects/list'),
            api.post('/api/datasources/list')
        ]);
        setProjects(projRes.data);
        setDataSources(dsRes.data);
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
    try {
      await api.post('/api/projects', values);
      message.success('项目创建成功');
      setIsModalOpen(false);
      form.resetFields();
      fetchData();
    } catch (error) {
      message.error('创建失败');
    }
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
            <Title level={2} style={{ marginBottom: 0 }}>项目列表</Title>
            <Text type="secondary">管理您的数据分析项目工作区</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => setIsModalOpen(true)}>
          新建项目
        </Button>
      </div>

      {projects.length === 0 && !loading ? (
        <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
                <span style={{color: '#888'}}>
                    暂无项目，请先创建一个
                </span>
            }
        >
            <Button type="primary" onClick={() => setIsModalOpen(true)}>立即创建</Button>
        </Empty>
      ) : (
        <Row gutter={[24, 24]}>
            {projects.map((item) => (
                <Col key={item.id} xs={24} sm={12} md={8} lg={8} xl={6}>
                    <Card 
                        hoverable
                        style={{ borderRadius: 12, overflow: 'hidden', border: '1px solid #f0f0f0', height: '100%' }}
                        styles={{ body: { padding: 24 } }}
                        actions={[
                            <Button type="link" onClick={() => navigate(`/chat/${item.id}`)}>
                                进入分析 <RightOutlined />
                            </Button>
                        ]}
                    >
                        <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 16 }}>
                            <div style={{ 
                                width: 48, height: 48, 
                                borderRadius: 8, 
                                background: '#e6f7ff', 
                                color: '#1890ff',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                marginRight: 16,
                                fontSize: 24,
                                flexShrink: 0
                            }}>
                                <ProjectOutlined />
                            </div>
                            <div style={{ overflow: 'hidden' }}>
                                <Title level={4} style={{ margin: 0, marginBottom: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={item.name}>{item.name}</Title>
                                <Space size={4}>
                                    <Tag icon={<DatabaseOutlined />} color="cyan" style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        {dataSources.find(d => d.id === item.data_source_id)?.name || '未知数据源'}
                                    </Tag>
                                </Space>
                            </div>
                        </div>
                        <div style={{ color: '#8c8c8c', fontSize: 13, height: 40, overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                            基于 {dataSources.find(d => d.id === item.data_source_id)?.name} 的数据分析项目。
                        </div>
                    </Card>
                </Col>
            ))}
        </Row>
      )}

      <Modal
        title="新建项目"
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={null}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label="项目名称" rules={[{ required: true }]}>
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item name="data_source_id" label="关联数据源" rules={[{ required: true }]}>
            <Select placeholder="请选择数据源">
              {dataSources.map(ds => (
                <Option key={ds.id} value={ds.id}>{ds.name}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <Button onClick={() => setIsModalOpen(false)}>取消</Button>
                <Button type="primary" htmlType="submit">创建</Button>
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ProjectPage;
