from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional,Dict, Any
import os

class APISettings(BaseSettings):

    """API配置"""
    glodonai_api_key: str = Field(default="hxHkv8BS0a1MDlsL", env ="GLODONAI_API_KEY")
    glodonai_api_secret: str = Field(default="1X51L2RULJuTGyY0x18uss1p", env ="GLODONAI_API_SECRET")
    glodonai_host: Optional[str] = Field(default="https://copilot.glodon.com", env ="GLODONAI_HOST")
    glodonai_get_token_url: Optional[str] = Field(default="https://copilot.glodon.com/api/auth/v1/access-token", env ="GLODONAI_GET_TOKEN_URL")
    glodonai_llm_url: Optional[str] = Field(default="https://copilot.glodon.com/api/cvforce/aishop/v1/chat/completions", env ="GLODONAI_LLM_URL")
    glodonai_llm_model: Optional[str] = Field(default="Aswhlbydjge0c", env ="GLODONAI_LLM_MODEL")
    glodonai_embedding_url: str = Field(default="https://copilot.glodon.com/api/cvforce/aishop/v1/embeddings", env="GLODONAI_EMBEDDING_URL")

class DatabaseSettings(BaseSettings):
     
    """数据库配置"""
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", env="NEO4J_USERNAME")
    neo4j_password: str = Field(default="password123", env="NEO4J_PASSWORD")
    chroma_persist_dir: str = Field(default="./chroma_db", env="CHROMA_PERSIST_DIR")

class SystemSettings(BaseSettings):
    """系统配置"""
    codebase_path: str = Field(default="J://gbmp//source//GcmpTests", env="CODEBASE_PATH")
    max_context_tokens: int = Field(default=8000, env="MAX_CONTEXT_TOKENS")
    max_files_per_query: int = Field(default=5, env="MAX_FILES_PER_QUERY")
    chunk_size: int = Field(default=2000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, env="CHUNK_OVERLAP")

    @validator("codebase_path")
    def validate_codebase_path(cls,v):
        if not v:
            raise ValueError("代码库路径必须设置")
        if not os.path.exists(v):
            raise ValueError(f"代码库路径不存在: {v}")
        return v


class Settings(BaseSettings):
    api: APISettings=Field(default_factory=APISettings)
    db : DatabaseSettings = Field(default_factory=DatabaseSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)

    class Config():
        env_file=".env"
        case_sensitive = True
        use_enum_values = True

setting = Settings()

class ConfigManager:  
    """配置管理器（兼容性包装器）"""

    def __init__(self):
        self.api = setting.api
        self.db = setting.db
        self.system = setting.system
    
    def validate(self):
        """验证配置完整性"""
        errors = []
        
        # 验证Neo4j连接
        try:
            from py2neo import Graph
            Graph(self.db.neo4j_uri, auth=(self.db.neo4j_username, self.db.neo4j_password))
        except Exception as e:
            errors.append(f"Neo4j连接失败: {e}")
        
        if errors:
            raise ValueError("配置错误: " + "; ".join(errors))
        
        print("✓ 配置验证通过")
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'api': {
                'glodonai_api_key': self.api.glodonai_api_key if self.api.glodonai_api_key else '',
                'glodonai_api_secret': self.api.glodonai_api_secret,
                'glodonai_host': self.api.glodonai_host,
                'glodonai_get_token_url': self.api.glodonai_get_token_url,
                'glodonai_llm_url': self.api.glodonai_llm_url,
                'glodonai_llm_model': self.api.glodonai_llm_model,
                'glodonai_embedding_url': self.api.glodonai_embedding_url
            },
            'db': {
                'neo4j_uri': self.db.neo4j_uri,
                'neo4j_username': self.db.neo4j_username,
                'neo4j_password': '***',
                'chroma_persist_dir': self.db.chroma_persist_dir
            },
            'system': {
                'codebase_path': self.system.codebase_path,
                'max_context_tokens': self.system.max_context_tokens,
                'max_files_per_query': self.system.max_files_per_query,
                'chunk_size': self.system.chunk_size,
                'chunk_overlap': self.system.chunk_overlap
            }
        }
    
    def print_config(self):
        """打印配置信息"""
        config_dict = self.to_dict()
        print("系统配置:")
        print(f"  代码库路径: {config_dict['system']['codebase_path']}")
        print(f"  模型: {config_dict['api']['glodonai_llm_model']}")
        print(f"  向量存储: {config_dict['db']['chroma_persist_dir']}")
        print(f"  图数据库: {config_dict['db']['neo4j_uri']}")

def get_settings() ->Settings:
    return setting

def get_config_manager() -> ConfigManager:
    return ConfigManager()
