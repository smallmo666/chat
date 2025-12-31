from pydantic import BaseModel
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from src.core.database import get_app_db, AppDatabase
from src.core.models import User
from src.core.security import verify_password, get_password_hash, create_access_token
from src.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class UserCreate(BaseModel):
    username: str
    password: str
    email: str = None

class UserRead(BaseModel):
    id: int
    username: str
    email: str = None
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", response_model=UserRead)
def register(user_in: UserCreate, app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        # Check if user exists
        existing = session.exec(select(User).where(User.username == user_in.username)).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Username already registered"
            )
        
        db_user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            role="user" # default role
        )
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return db_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), app_db: AppDatabase = Depends(get_app_db)):
    with app_db.get_session() as session:
        # In OAuth2, 'username' field is used for login, which can be email or username
        user = session.exec(select(User).where(User.username == form_data.username)).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
             raise HTTPException(status_code=400, detail="Inactive user")
             
        access_token = create_access_token(subject=str(user.id))
        return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
