from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, JSON

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
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Project(SQLModel, table=True):
    __tablename__ = "projects"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    data_source_id: int = Field(foreign_key="data_sources.id")
    scope_config: Optional[dict] = Field(default={}, sa_type=JSON) # e.g., {"tables": ["t1", "t2"], "schemas": ["s1"]}
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
