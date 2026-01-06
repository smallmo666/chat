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

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Security Check on Startup
if settings.SECRET_KEY == "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY":
    # In a real production app, we might want to raise an error or sys.exit
    # But for development convenience, we just print a warning.
    # Check if we are running in production mode (e.g. via an ENV var)
    env_mode = os.getenv("ENV", "development")
    if env_mode.lower() == "production":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!! CRITICAL SECURITY WARNING: You are using the default SECRET_KEY in PRODUCTION !!")
        print("!! Please set the SECRET_KEY environment variable immediately.                 !!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        # raise ValueError("Default SECRET_KEY usage is prohibited in production environment.")
    else:
        print("WARNING: Using default SECRET_KEY. This is unsafe for production.")
