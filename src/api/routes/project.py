import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from src.core.database import get_app_db, get_query_db, AppDatabase
from src.core.redis_client import get_sync_redis_client
import hashlib
import json
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
    refresh_cache: bool = False
    page: int = 1
    size: int = 200
    db_prefix: Optional[str] = None

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
            # If refresh, clear shard keys and overall key
            if request.refresh_cache:
                try:
                    r = get_sync_redis_client()
                    scope_str = json.dumps(scope, sort_keys=True) if scope else "full"
                    scope_hash = hashlib.md5(scope_str.encode()).hexdigest()
                    overall_key = f"t2s:v1:schema:{project_id}:{scope_hash}"
                    r.delete(overall_key)
                    prefix = f"t2s:v1:schema_shard:{project_id}:{scope_hash}:"
                    for k in r.scan_iter(prefix + "*"):
                        try:
                            r.delete(k)
                        except Exception:
                            pass
                except Exception as _:
                    pass
            schema_json = query_db.inspect_schema(scope, project_id=project_id, refresh=request.refresh_cache)
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
        
        # Optional db prefix filter
        if request.db_prefix:
            prefix = request.db_prefix.strip()
            tables_list = [t for t in tables_list if t["name"].startswith(prefix + ".")]
        
        tables_list.sort(key=lambda x: x["name"])
        total = len(tables_list)
        page = max(1, request.page)
        size = max(1, request.size)
        start = (page - 1) * size
        end = start + size
        sliced = tables_list[start:end]
        
        # Progress: completed dbs vs total dbs
        completed_dbs = set()
        for t in tables_list:
            try:
                dbn = t["name"].split(".")[0]
                completed_dbs.add(dbn)
            except Exception:
                pass
        total_dbs = 1
        try:
            # Derive total dbs from scope or datasource
            if scope and isinstance(scope, dict) and scope.get("databases"):
                total_dbs = len(scope.get("databases"))
            elif query_db.dbname:
                total_dbs = 1
            else:
                total_dbs = len(query_db._get_databases())
        except Exception:
            pass
        
        return {
            "tables": sliced,
            "total": total,
            "page": page,
            "size": size,
            "progress": {
                "completed_dbs": len(completed_dbs),
                "total_dbs": total_dbs
            }
        }
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
