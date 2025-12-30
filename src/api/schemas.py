from typing import Optional, List
from pydantic import BaseModel

# --- DataSource Schemas ---
class DataSourceCreate(BaseModel):
    name: str
    type: str = "postgresql"
    host: str
    port: int
    user: str
    password: str
    dbname: str

class DataSourceRead(BaseModel):
    id: int
    name: str
    type: str
    host: str
    port: int
    user: str
    dbname: str

# --- Project Schemas ---
class ProjectCreate(BaseModel):
    name: str
    data_source_id: int
    scope_config: Optional[dict] = {}

class ProjectRead(BaseModel):
    id: int
    name: str
    data_source_id: int
    scope_config: dict

# --- Chat Schemas ---
class ChatRequest(BaseModel):
    message: str
    project_id: Optional[int] = None
    thread_id: Optional[str] = None
    selected_tables: Optional[list[str]] = None
    
    # HITL Control
    command: Optional[str] = "start" # start, approve, edit
    modified_sql: Optional[str] = None

# --- Audit/Feedback Schemas ---
class FeedbackRequest(BaseModel):
    audit_id: int
    rating: int # 1 or -1
    comment: Optional[str] = None
