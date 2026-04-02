from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import secrets


class Settings(BaseSettings):

    # 应用配置
    APP_NAME :str = Field(default="Enterprise FastAPI App", env ="APP_NAME")
    DEBUG : bool = Field(default=True, env = "DEBUG")
    SECRET_KEY: str = Field(default_factory= lambda: secrets.token_urlsafe(32),env = "SECRET_KEY")
    ALGORITHM : str =Field(default="HS256", env ="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES :int =Field(default=30, env = "ACCESS_TOKEN_EXPIRE_MINUTES")

    # 数据库配置
    MONGODB_URL : str =Field(default= "mongodb://10.5.67.100:27017", env = "MONGODB_URL")
    DATABASE_NAME : str = Field(default="apiinfo", env ="DATABASE_NAME")

    # MongoDB配置
    MONGO_ROOT_USERNAME: str= Field(default="admin",env="MONGO_ROOT_USERNAME") 
    MONGO_ROOT_PASSWORD: str= Field(default="password",env ="MONGO_ROOT_PASSWORD") 

    # CORS配置
    ALLOWED_ORIGINS: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    
    # 前端配置
    VITE_API_BASE_URL: str =Field(default="http://localhost:8000/api/v1", env ="VITE_API_BASE_URL")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # 监控配置
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    PROMETHEUS_MULTIPROC_DIR: str =Field(default="/tmp", env ="PROMETHEUS_MULTIPROC_DIR")
    
    # 安全配置
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # Grafana配置
    GRAFANA_PASSWORD: str =Field(default="admin123",env ="GRAFANA_PASSWORD")
    # API配置
    API_V1_STR: str = Field(default="/api/v1", env="API_V1_STR")

    class Config:
        env_file = ".env"
        case_sensitive = True
        use_enum_values = True

settings = Settings()

def get_settings() ->Settings:
    return settings





















