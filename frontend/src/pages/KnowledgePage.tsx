import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Tag, Card, Typography, App } from 'antd';
import { PlusOutlined, DeleteOutlined, BookOutlined } from '@ant-design/icons';
import { useTheme } from '../context/ThemeContext';

interface KnowledgeItem {
    id: number;
    term: string;
    definition: string;
    formula?: string;
    tags: string[];
    created_at: string;
}

const KnowledgePage: React.FC = () => {
    const { message } = App.useApp();
    const { isDarkMode } = useTheme();
    const [data, setData] = useState<KnowledgeItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [form] = Form.useForm();

    const fetchKnowledge = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/api/knowledge', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (response.ok) {
                const result = await response.json();
                setData(result);
            }
        } catch (error) {
            message.error('获取知识库失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchKnowledge();
    }, []);

    const handleSubmit = async (values: any) => {
        try {
            const token = localStorage.getItem('token');
            // Parse tags
            const tags = values.tags ? values.tags.split(',').map((t: string) => t.trim()) : [];
            
            const response = await fetch('/api/knowledge', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    term: values.term,
                    definition: values.definition,
                    formula: values.formula,
                    tags: tags
                })
            });

            if (response.ok) {
                message.success('添加成功');
                setIsModalOpen(false);
                form.resetFields();
                fetchKnowledge();
            } else {
                message.error('添加失败');
            }
        } catch (error) {
            message.error('请求失败');
        }
    };

    const handleDelete = async (id: number) => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`/api/knowledge/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                message.success('删除成功');
                fetchKnowledge();
            } else {
                message.error('删除失败');
            }
        } catch (error) {
            message.error('请求失败');
        }
    };

    const columns = [
        {
            title: '术语 (Term)',
            dataIndex: 'term',
            key: 'term',
            width: '20%',
            render: (text: string) => <span style={{ fontWeight: 600 }}>{text}</span>
        },
        {
            title: '定义 (Definition)',
            dataIndex: 'definition',
            key: 'definition',
        },
        {
            title: '公式 (Formula)',
            dataIndex: 'formula',
            key: 'formula',
            render: (text: string) => text ? <code style={{ background: isDarkMode ? '#333' : '#f0f0f0', padding: '2px 6px', borderRadius: 4 }}>{text}</code> : '-'
        },
        {
            title: '标签',
            dataIndex: 'tags',
            key: 'tags',
            render: (tags: string[]) => (
                <>
                    {tags && tags.map(tag => (
                        <Tag key={tag} color="blue">{tag}</Tag>
                    ))}
                </>
            ),
        },
        {
            title: '操作',
            key: 'action',
            width: 100,
            render: (_: any, record: KnowledgeItem) => (
                <Button 
                    type="text" 
                    danger 
                    icon={<DeleteOutlined />} 
                    onClick={() => handleDelete(record.id)} 
                />
            ),
        },
    ];

    return (
        <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <div>
                    <Typography.Title level={2} style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
                        <BookOutlined /> 业务知识库
                    </Typography.Title>
                    <Typography.Text type="secondary">
                        管理业务术语、计算逻辑和指标定义。Agent 将使用这些知识来提高 SQL 生成的准确性。
                    </Typography.Text>
                </div>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)} size="large">
                    添加知识
                </Button>
            </div>

            <Card styles={{ body: { padding: 0 } }} bordered={false}>
                <Table 
                    columns={columns} 
                    dataSource={data} 
                    rowKey="id" 
                    loading={loading}
                    pagination={{ pageSize: 10 }}
                />
            </Card>

            <Modal
                title="添加新知识"
                open={isModalOpen}
                onCancel={() => setIsModalOpen(false)}
                footer={null}
            >
                <Form
                    form={form}
                    layout="vertical"
                    onFinish={handleSubmit}
                >
                    <Form.Item
                        name="term"
                        label="术语名称"
                        rules={[{ required: true, message: '请输入术语名称' }]}
                        help="例如：ROI, 高价值用户, GMV"
                    >
                        <Input placeholder="输入业务术语..." />
                    </Form.Item>
                    
                    <Form.Item
                        name="definition"
                        label="定义描述"
                        rules={[{ required: true, message: '请输入定义' }]}
                        help="清晰描述该术语的业务含义"
                    >
                        <Input.TextArea rows={4} placeholder="例如：投资回报率，计算方式为..." />
                    </Form.Item>
                    
                    <Form.Item
                        name="formula"
                        label="计算公式 (可选)"
                        help="如果是计算指标，请提供 SQL 片段或数学公式"
                    >
                        <Input placeholder="(revenue - cost) / cost" />
                    </Form.Item>
                    
                    <Form.Item
                        name="tags"
                        label="标签"
                        help="用逗号分隔，例如：财务, 销售"
                    >
                        <Input placeholder="财务, 核心指标" />
                    </Form.Item>
                    
                    <Form.Item>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                            <Button onClick={() => setIsModalOpen(false)}>取消</Button>
                            <Button type="primary" htmlType="submit">保存</Button>
                        </div>
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default KnowledgePage;
