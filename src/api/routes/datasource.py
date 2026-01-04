from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from src.core.database import get_app_db, AppDatabase, QueryDatabase
from src.core.models import DataSource, User
from src.api.schemas import DataSourceCreate, DataSourceRead
from src.core.security_auth import get_current_user

router = APIRouter(prefix="/datasources", tags=["datasource"])

@router.post("", response_model=DataSourceRead)
def create_datasource(
    datasource: DataSourceCreate, 
    app_db: AppDatabase = Depends(get_app_db),
    current_user: User = Depends(get_current_user)
):

    with app_db.get_session() as session:
        # Check uniqueness (only for user's datasources ideally, but name is unique globally in model)
        # We might want to make name unique per user, but for now global is fine
        existing = session.exec(select(DataSource).where(DataSource.name == datasource.name)).first()
        if existing:
            raise HTTPException(status_code=400, detail="DataSource with this name already exists")
            
        db_ds = DataSource.from_orm(datasource)
        db_ds.owner_id = current_user.id
        session.add(db_ds)
        session.commit()
        session.refresh(db_ds)
        return db_ds

@router.put("/{id}", response_model=DataSourceRead)
def update_datasource(id: int, ds: DataSourceCreate, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        db_ds = session.get(DataSource, id)
        if not db_ds:
            raise HTTPException(status_code=404, detail="DataSource not found")
        
        # Update fields
        db_ds.name = ds.name
        db_ds.type = ds.type
        db_ds.host = ds.host
        db_ds.port = ds.port
        db_ds.user = ds.user
        db_ds.password = ds.password
        db_ds.dbname = ds.dbname
        
        session.add(db_ds)
        session.commit()
        session.refresh(db_ds)
        return db_ds

@router.post("/test")
async def test_datasource_connection(ds: DataSourceCreate):
    from sqlalchemy import text
    try:
        # Temporarily create a DataSource object (not saved to DB)
        temp_ds = DataSource(
            name="test",
            type=ds.type,
            host=ds.host,
            port=ds.port,
            user=ds.user,
            password=ds.password,
            dbname=ds.dbname
        )
        # Try to initialize QueryDatabase which establishes connection
        db = QueryDatabase(temp_ds)
        # Verify connection with a simple query using async engine
        async with db.async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ok": True, "message": "Connection successful"}
    except Exception as e:
        print(f"Test connection failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[DataSourceRead])
def get_datasources(
    app_db: AppDatabase = Depends(get_app_db),
    current_user: User = Depends(get_current_user)
):
    with app_db.get_session() as session:
        if current_user.role == "admin":
            datasources = session.exec(select(DataSource)).all()
        else:
             datasources = session.exec(select(DataSource).where(DataSource.owner_id == current_user.id)).all()
        return datasources

@router.delete("/{id}")
def delete_datasource(id: int, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        ds = session.get(DataSource, id)
        if not ds:
            raise HTTPException(status_code=404, detail="DataSource not found")
        session.delete(ds)
        session.commit()
        return {"ok": True}
