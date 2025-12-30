from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlmodel import Session, select

from src.core.database import get_app_db, AppDatabase
from src.core.models import User
from src.core.security import SECRET_KEY, ALGORITHM

# Token URL points to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    app_db: AppDatabase = Depends(get_app_db)
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = payload.get("sub")
        if token_data is None:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = int(token_data)
    except (JWTError, ValidationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    with app_db.get_session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.is_active:
             raise HTTPException(status_code=400, detail="Inactive user")
        return user
