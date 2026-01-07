import os
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    全局配置类。
    优先从环境变量读取。
    """
    # Environment
    ENV: str = Field(default="development", env="ENV")

    # Security
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24, env="ACCESS_TOKEN_EXPIRE_MINUTES") # 1 Day default

    # Database
    APP_DB_URL: str = Field(..., env="APP_DB_URL")
    
    # LLM
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    OPENAI_MODEL_NAME: str = Field(default="gpt-4o", env="OPENAI_MODEL_NAME")
    OPENAI_API_BASE: str = Field(default="", env="OPENAI_API_BASE")
    
    # Embedding
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")

    # CORS
    CORS_ORIGINS: list[str] = Field(default=["*"], env="CORS_ORIGINS")

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    REDIS_SCHEMA_TTL: int = Field(default=3600, env="REDIS_SCHEMA_TTL")
    REDIS_SQL_TTL: int = Field(default=300, env="REDIS_SQL_TTL")
    
    # ChromaDB (Remote)
    CHROMA_SERVER_HOST: str = Field(default="159.75.148.55", env="CHROMA_SERVER_HOST")
    CHROMA_SERVER_PORT: int = Field(default=8000, env="CHROMA_SERVER_PORT")
    CHROMA_USE_REMOTE: bool = Field(default=True, env="CHROMA_USE_REMOTE")

    # Query DB Pool
    QUERY_POOL_SIZE: int = Field(default=10, env="QUERY_POOL_SIZE")
    QUERY_MAX_OVERFLOW: int = Field(default=20, env="QUERY_MAX_OVERFLOW")
    QUERY_POOL_RECYCLE: int = Field(default=3600, env="QUERY_POOL_RECYCLE")
    ROUTE_POOL_SIZE: int = Field(default=5, env="ROUTE_POOL_SIZE")
    ROUTE_MAX_OVERFLOW: int = Field(default=10, env="ROUTE_MAX_OVERFLOW")
    DEFAULT_ROW_LIMIT: int = Field(default=1000, env="DEFAULT_ROW_LIMIT")
    CHECKPOINT_BATCH_SIZE: int = Field(default=10, env="CHECKPOINT_BATCH_SIZE")
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    PREVIEW_ROW_COUNT: int = Field(default=100, env="PREVIEW_ROW_COUNT")
    DOWNLOAD_TTL: int = Field(default=600, env="DOWNLOAD_TTL")
    ENABLE_RATE_LIMIT: bool = Field(default=True, env="ENABLE_RATE_LIMIT")
    RATE_LIMIT_WINDOW: int = Field(default=60, env="RATE_LIMIT_WINDOW")
    RATE_LIMIT_MAX_REQUESTS: int = Field(default=120, env="RATE_LIMIT_MAX_REQUESTS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Security Check on Startup
if settings.SECRET_KEY == "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY":
    if settings.ENV.lower() == "production":
        raise ValueError("Default SECRET_KEY usage is prohibited in production.")
    else:
        print("WARNING: Using default SECRET_KEY. This is unsafe for production.")

# CORS production guard
if settings.ENV.lower() == "production":
    if any(origin == "*" for origin in (settings.CORS_ORIGINS or [])):
        raise ValueError("Wildcard CORS origins are prohibited in production.")
