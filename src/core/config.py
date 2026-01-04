import os
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    全局配置类。
    优先从环境变量读取。
    """
    # Security
    SECRET_KEY: str = Field(default="CHANGE_THIS_IN_PRODUCTION_SECRET_KEY", env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24, env="ACCESS_TOKEN_EXPIRE_MINUTES") # 1 Day default

    # Database
    APP_DB_URL: str = Field(default="mysql+pymysql://testdb:123456@159.75.148.55:3306/testdb", env="APP_DB_URL")
    
    # LLM
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    OPENAI_MODEL_NAME: str = Field(default="gpt-4o", env="OPENAI_MODEL_NAME")
    OPENAI_API_BASE: str = Field(default="", env="OPENAI_API_BASE")
    
    # Embedding
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")

    # CORS
    CORS_ORIGINS: list[str] = Field(default=["*"], env="CORS_ORIGINS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
