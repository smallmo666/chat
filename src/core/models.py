from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, JSON
from sqlalchemy import Text

# --- Phase 10: Multi-Tenancy Models ---

class Organization(SQLModel, table=True):
    """
    组织模型 (多租户根节点)。
    """
    __tablename__ = "organizations"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="组织 ID")
    name: str = Field(index=True, unique=True, description="组织名称")
    owner_id: int = Field(foreign_key="app_users.id", description="创建者 ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class Knowledge(SQLModel, table=True):
    """
    业务知识库模型。
    存储业务术语、计算公式和定义。
    """
    __tablename__ = "knowledge_base"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: Optional[int] = Field(default=None, foreign_key="organizations.id", description="所属组织 ID")
    term: str = Field(index=True, description="术语名称")
    definition: str = Field(description="定义或描述")
    formula: Optional[str] = Field(None, description="计算公式 (SQL/Math)")
    tags: Optional[List[str]] = Field(default=[], sa_type=JSON, description="标签")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Dashboard(SQLModel, table=True):
    """
    仪表盘模型。
    存储用户自定义的看板布局。
    """
    __tablename__ = "dashboards"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    user_id: int = Field(foreign_key="app_users.id")
    title: str = Field(description="仪表盘标题")
    layout: dict = Field(default={}, sa_type=JSON, description="Grid 布局配置")
    charts: List[dict] = Field(default=[], sa_type=JSON, description="图表配置列表")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class OrganizationMember(SQLModel, table=True):
    """
    组织成员关联表。
    """
    __tablename__ = "organization_members"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", index=True)
    user_id: int = Field(foreign_key="app_users.id", index=True)
    role: str = Field(default="member", description="组织内角色 (admin, member)")
    joined_at: datetime = Field(default_factory=datetime.utcnow)

# --------------------------------------

class User(SQLModel, table=True):
    """
    用户模型。
    存储应用程序用户及其角色信息。
    """
    __tablename__ = "app_users"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="用户唯一标识")
    username: str = Field(index=True, unique=True, description="用户名")
    email: Optional[str] = Field(default=None, index=True, description="电子邮件")
    hashed_password: str = Field(..., description="哈希密码")
    is_active: bool = Field(default=True, description="账户是否激活")
    role: str = Field(default="user", description="系统级角色 (user, admin)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class DataSource(SQLModel, table=True):
    """
    数据源模型。
    定义外部数据库连接配置。
    """
    __tablename__ = "data_sources"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="数据源 ID")
    organization_id: Optional[int] = Field(default=None, foreign_key="organizations.id", description="所属组织 ID") # Multi-tenancy
    name: str = Field(index=True, unique=True, description="数据源名称")
    type: str = Field(default="postgresql", description="数据库类型 (postgresql, mysql 等)")
    host: str = Field(..., description="主机地址")
    port: int = Field(..., description="端口号")
    user: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")
    dbname: Optional[str] = Field(default=None, description="数据库名称 (可选，若为空则展示所有库)")
    owner_id: Optional[int] = Field(default=None, foreign_key="app_users.id", description="创建者 ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class Project(SQLModel, table=True):
    """
    项目模型。
    关联数据源和特定配置。
    """
    __tablename__ = "projects"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="项目 ID")
    organization_id: Optional[int] = Field(default=None, foreign_key="organizations.id", description="所属组织 ID") # Multi-tenancy
    name: str = Field(index=True, description="项目名称")
    data_source_id: int = Field(foreign_key="data_sources.id", description="关联数据源 ID")
    owner_id: Optional[int] = Field(default=None, foreign_key="app_users.id", description="所有者 ID")
    scope_config: Optional[dict] = Field(default={}, sa_type=JSON, description="作用域配置 (例如: 指定表或 Schema)")
    
    # 节点级模型路由配置
    # 示例: {"GenerateDSL": 1, "PythonAnalysis": 2}，值为 LLMProvider ID
    node_model_config: Optional[dict] = Field(default={}, sa_type=JSON, description="节点模型路由配置")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class LLMProvider(SQLModel, table=True):
    """
    LLM 提供商配置模型。
    管理不同模型提供商的 API 密钥和参数。
    """
    __tablename__ = "llm_providers"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="配置 ID")
    organization_id: Optional[int] = Field(default=None, foreign_key="organizations.id", description="所属组织 ID") # Multi-tenancy
    name: str = Field(index=True, unique=True, description="配置名称 (例如: 'Production GPT-4')")
    provider: str = Field(default="openai", description="提供商 (openai, azure, anthropic, ollama, vllm)")
    model_name: str = Field(..., description="模型名称 (例如: gpt-4o, claude-3-5-sonnet)")
    
    api_base: Optional[str] = Field(None, description="API 基础 URL (用于 Azure/Ollama/vLLM)")
    api_key: Optional[str] = Field(None, description="API 密钥 (生产环境应加密存储)")
    
    # 额外配置，如 temperature, max_tokens 等
    parameters: Optional[dict] = Field(default={}, sa_type=JSON, description="模型额外参数")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class AuditLog(SQLModel, table=True):
    """
    审计日志模型。
    记录用户交互、执行的 SQL、性能指标和成本。
    """
    __tablename__ = "audit_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="日志 ID")
    project_id: Optional[int] = Field(default=None, foreign_key="projects.id", description="关联项目 ID")
    user_id: Optional[int] = Field(default=None, foreign_key="app_users.id", description="执行用户 ID") # Audit user
    session_id: str = Field(index=True, description="会话 ID")
    user_query: str = Field(..., description="用户查询内容")
    plan: Optional[dict] = Field(default=None, sa_type=JSON, description="执行计划快照")
    executed_sql: Optional[str] = Field(None, sa_type=Text, description="执行的 SQL 语句")
    generated_dsl: Optional[str] = Field(None, description="生成的 DSL (JSON)") 
    result_summary: Optional[str] = Field(None, description="结果摘要或状态")
    duration_ms: int = Field(default=0, description="执行耗时 (毫秒)")
    status: str = Field(default="success", description="执行状态 (success, error)")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    # 成本追踪
    total_tokens: int = Field(default=0, description="总消耗 Token 数")
    estimated_cost: float = Field(default=0.0, description="预估成本")
    
    # 反馈
    feedback_rating: Optional[int] = Field(default=None, description="用户评分 (1: 好, -1: 差)")
    feedback_comment: Optional[str] = Field(default=None, description="用户反馈评论")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class ChatSession(SQLModel, table=True):
    """
    会话模型。
    管理用户会话元数据。
    """
    __tablename__ = "chat_sessions"
    
    id: str = Field(primary_key=True, description="会话 ID (Thread ID)")
    user_id: int = Field(index=True, description="用户 ID")
    project_id: int = Field(index=True, description="项目 ID")
    title: str = Field(default="新会话", description="会话标题")
    is_active: bool = Field(default=True, description="是否活跃 (软删除)")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
