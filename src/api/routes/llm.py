from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from src.core.database import get_app_db, AppDatabase
from src.core.models import LLMProvider, User
from src.api.schemas_llm import LLMProviderCreate, LLMProviderRead
from src.core.security_auth import get_current_user

router = APIRouter(prefix="/api/llms", tags=["llm"])

@router.post("", response_model=LLMProviderRead)
def create_llm_provider(
    llm: LLMProviderCreate, 
    app_db: AppDatabase = Depends(get_app_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
         # Optionally restrict LLM creation to admins
         pass 

    with app_db.get_session() as session:
        # Check uniqueness
        existing = session.exec(select(LLMProvider).where(LLMProvider.name == llm.name)).first()
        if existing:
            raise HTTPException(status_code=400, detail="LLM Provider with this name already exists")
            
        db_llm = LLMProvider.from_orm(llm)
        session.add(db_llm)
        session.commit()
        session.refresh(db_llm)
        return db_llm

@router.get("", response_model=List[LLMProviderRead])
def get_llm_providers(app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        providers = session.exec(select(LLMProvider)).all()
        return providers

@router.put("/{id}", response_model=LLMProviderRead)
def update_llm_provider(
    id: int, 
    llm: LLMProviderCreate, 
    app_db: AppDatabase = Depends(get_app_db),
    current_user: User = Depends(get_current_user)
):
    with app_db.get_session() as session:
        db_llm = session.get(LLMProvider, id)
        if not db_llm:
            raise HTTPException(status_code=404, detail="LLM Provider not found")
            
        db_llm.name = llm.name
        db_llm.provider = llm.provider
        db_llm.model_name = llm.model_name
        db_llm.api_base = llm.api_base
        if llm.api_key: # Only update if provided
            db_llm.api_key = llm.api_key
        db_llm.parameters = llm.parameters
        
        session.add(db_llm)
        session.commit()
        session.refresh(db_llm)
        return db_llm

@router.delete("/{id}")
def delete_llm_provider(
    id: int, 
    app_db: AppDatabase = Depends(get_app_db),
    current_user: User = Depends(get_current_user)
):
    with app_db.get_session() as session:
        db_llm = session.get(LLMProvider, id)
        if not db_llm:
            raise HTTPException(status_code=404, detail="LLM Provider not found")
        session.delete(db_llm)
        session.commit()
        return {"ok": True}
