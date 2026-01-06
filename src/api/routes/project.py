import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from src.core.database import get_app_db, get_query_db, AppDatabase
from src.core.models import Project, User
from src.api.schemas import ProjectCreate, ProjectRead
from src.domain.schema.value import get_value_searcher
from src.core.security_auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", response_model=ProjectRead)
def create_project(
    proj: ProjectCreate,
    app_db: AppDatabase = Depends(get_app_db),
    current_user: User = Depends(get_current_user),
):
    with app_db.get_session() as session:
        db_proj = Project.from_orm(proj)
        db_proj.owner_id = current_user.id
        session.add(db_proj)
        session.commit()
        session.refresh(db_proj)
        return db_proj

from pydantic import BaseModel

class ProjectTablesRequest(BaseModel):
    project_id: Optional[int] = None

class ProjectIdRequest(BaseModel):
    id: int

@router.post("/list", response_model=List[ProjectRead])
def get_projects(
    app_db: AppDatabase = Depends(get_app_db),
    current_user: User = Depends(get_current_user),
):
    with app_db.get_session() as session:
        if current_user.role == "admin":
            projects = session.exec(select(Project)).all()
        else:
            projects = session.exec(select(Project).where(Project.owner_id == current_user.id)).all()
        return projects

@router.post("/tables")
def get_tables(request: ProjectTablesRequest, app_db: AppDatabase = Depends(get_app_db)):
    """
    Get tables for schema browser.
    """
    try:
        project_id = request.project_id
        if project_id:
            query_db = get_query_db(project_id)
            
            # Get Project Scope
            with app_db.get_session() as session:
                project = session.get(Project, project_id)
                scope = project.scope_config if project else None
            
            schema_json = query_db.inspect_schema(scope)
        else:
            query_db = get_query_db() # Default env
            schema_json = query_db.inspect_schema()

        if not schema_json:
            return {"tables": []}
            
        schema_data = json.loads(schema_json)
        
        tables_list = []
        for name, info in schema_data.items():
            if isinstance(info, list):
                tables_list.append({
                    "name": name,
                    "comment": "",
                    "columns": info
                })
            else:
                tables_list.append({
                    "name": name,
                    "comment": info.get("comment", ""),
                    "columns": info.get("columns", [])
                })
        
        tables_list.sort(key=lambda x: x["name"])
        return {"tables": tables_list}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/get", response_model=ProjectRead)
def get_project(request: ProjectIdRequest, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        proj = session.get(Project, request.id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        return proj

@router.post("/{id}/index-values")
def index_project_values(id: int, app_db: AppDatabase = Depends(get_app_db)):
    """
    Trigger value indexing for Entity Linking.
    """
    # Check if project exists
    with app_db.get_session() as session:
        proj = session.get(Project, id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
            
    # Run indexing in background
    async def run_indexing():
        print(f"Starting background value indexing for project {id}...")
        try:
            searcher = get_value_searcher(id)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, searcher.index_values)
            print(f"Background value indexing for project {id} finished.")
        except Exception as e:
            print(f"Background value indexing failed: {e}")

    asyncio.create_task(run_indexing())
    
    return {"ok": True, "message": "Value indexing started in background."}
