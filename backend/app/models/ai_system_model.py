from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# ==================== 请求/响应模型 ====================
class InitializeRequest(BaseModel):
    """初始化请求"""
    force_rebuild: bool = Field(default=True, description="是否强制重建索引")
    codebase_path: Optional[str] = Field(None, description="代码库路径，为空使用配置路径")

class InitializeResponse(BaseModel):
    """初始化响应"""
    success: bool
    message: str
    system_id: Optional[str] = None
    initialization_time: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None

class QuestionRequest(BaseModel):
    """提问请求"""
    question: str = Field(..., min_length=1, max_length=1000, description="问题内容")
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    stream: bool = Field(default=False, description="是否启用流式响应")

class QuestionResponse(BaseModel):
    """提问响应"""
    success: bool
    answer: Optional[str] = None
    question: str
    session_id: str
    source_files: List[str] = []
    files_count: int = 0
    token_usage: Optional[Dict[str, int]] = None
    processing_time: float
    error: Optional[str] = None

class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    created_at: str
    last_active: str
    question_count: int
    conversation_history_count: int
    system_status: Dict[str, Any]

class SystemStatus(BaseModel):
    """系统状态"""
    initialized: bool
    initialization_time: Optional[str]
    codebase_info: Optional[Dict[str, Any]]
    vector_database_stats: Optional[Dict[str, Any]]
    graph_database_stats: Optional[Dict[str, Any]]
    active_sessions: int
    system_stats: Optional[Dict[str, Any]]

class DebugRetrievalRequest(BaseModel):
    """调试检索请求"""
    question: str = Field(..., min_length=1, max_length=500)
    max_files: int = Field(default=5, ge=1, le=20)

class DebugRetrievalResponse(BaseModel):
    """调试检索响应"""
    question: str
    retrieved_files: List[Dict[str, Any]]
    count: int
    processing_time: float