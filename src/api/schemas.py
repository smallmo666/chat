from typing import Optional
from pydantic import BaseModel

# --- DataSource Schemas ---
class DataSourceCreate(BaseModel):
    name: str
    type: str = "postgresql"
    host: str
    port: int
    user: str
    password: str
    dbname: Optional[str] = None

class DataSourceRead(BaseModel):
    id: int
    name: str
    type: str
    host: str
    port: int
    user: str
    # password field is intentionally excluded for security
    dbname: Optional[str] = None

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
    clarify_choices: Optional[list[str]] = None
    
    # HITL Control
    command: Optional[str] = "start"
    modified_sql: Optional[str] = None

class PythonExecRequest(BaseModel):
    code: str
    project_id: str

# --- Session Management Schemas ---
class SessionListRequest(BaseModel):
    project_id: int

class SessionHistoryRequest(BaseModel):
    session_id: str

class SessionDeleteRequest(BaseModel):
    session_id: str

class SessionUpdateRequest(BaseModel):
    session_id: str
    title: str

# --- Audit/Feedback Schemas ---
class FeedbackRequest(BaseModel):
    audit_id: int
    rating: int # 1 or -1
    comment: Optional[str] = None
