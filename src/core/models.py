from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, JSON

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    role: str = Field(default="user") # user, admin
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DataSource(SQLModel, table=True):
    __tablename__ = "data_sources"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    type: str = Field(default="postgresql")  # postgresql, mysql, etc.
    host: str
    port: int
    user: str
    password: str
    dbname: str
    owner_id: Optional[int] = Field(default=None, foreign_key="users.id") # Multi-tenancy
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Project(SQLModel, table=True):
    __tablename__ = "projects"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    data_source_id: int = Field(foreign_key="data_sources.id")
    owner_id: Optional[int] = Field(default=None, foreign_key="users.id") # Multi-tenancy
    scope_config: Optional[dict] = Field(default={}, sa_type=JSON) # e.g., {"tables": ["t1", "t2"], "schemas": ["s1"]}
    
    # Node-level Model Routing Configuration
    # Example: {"GenerateDSL": 1, "PythonAnalysis": 2} where values are LLMProvider IDs
    node_model_config: Optional[dict] = Field(default={}, sa_type=JSON)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class LLMProvider(SQLModel, table=True):
    __tablename__ = "llm_providers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True) # e.g., "Production GPT-4"
    provider: str = Field(default="openai") # openai, azure, anthropic, ollama, vllm
    model_name: str # e.g., gpt-4o, claude-3-5-sonnet, deepseek-coder
    
    api_base: Optional[str] = None
    api_key: Optional[str] = None # In prod, this should be encrypted
    
    # Additional config like temperature, max_tokens, etc.
    parameters: Optional[dict] = Field(default={}, sa_type=JSON)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = Field(default=None, foreign_key="projects.id")
    session_id: str = Field(index=True)
    user_query: str
    plan: Optional[dict] = Field(default=None, sa_type=JSON)
    executed_sql: Optional[str] = None
    result_summary: Optional[str] = None # Short summary or status
    duration_ms: int = Field(default=0)
    status: str = Field(default="success") # success, error
    error_message: Optional[str] = None
    
    # Cost Tracking
    total_tokens: int = Field(default=0)
    estimated_cost: float = Field(default=0.0)
    
    # Feedback
    feedback_rating: Optional[int] = Field(default=None) # 1 for up, -1 for down
    feedback_comment: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
