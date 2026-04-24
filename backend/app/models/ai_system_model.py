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

# ==================== 用例生成系统模型 ====================
class ParseDocumentResponse(BaseModel):
    """文档解析响应"""
    success: bool
    raw_content: str = ""
    format: str = "markdown"
    metadata: Dict[str, Any] = {}
    error: Optional[str] = None

class TestCaseGenRequest(BaseModel):
    """用例生成请求"""
    requirement_text: str = Field(..., min_length=1, description="需求文档文本内容")
    search_keyword: str = Field(default="", description="图谱检索关键词，为空则使用需求文本前50字")

class GraphNodeData(BaseModel):
    """知识图谱节点"""
    id: str
    name: str
    label: str
    type: str = "requirement"
    description: str = ""
    properties: Dict[str, Any] = {}

class GraphEdgeData(BaseModel):
    """知识图谱边"""
    source: str
    target: str
    label: str
    properties: Dict[str, Any] = {}

class TestCaseStep(BaseModel):
    """测试步骤"""
    action: str
    expected: str = ""

class TestCaseItem(BaseModel):
    """单条测试用例"""
    id: str = ""
    name: str = ""
    description: str = ""
    priority: str = "中"
    status: str = "未执行"
    preconditions: str = ""
    steps: List[TestCaseStep] = []
    module: str = ""
    created_at: str = ""
    updated_at: str = ""

class TestCaseGenResponse(BaseModel):
    """用例生成完整响应"""
    success: bool
    message: str = ""
    test_cases: List[TestCaseItem] = []
    graph_nodes: List[GraphNodeData] = []
    graph_edges: List[GraphEdgeData] = []
    processing_time: float = 0
    error: Optional[str] = None

# ==================== 异步任务模型 ====================
class SubmitTaskRequest(BaseModel):
    """提交异步任务请求"""
    task_type: str = Field(..., description="任务类型: parse_graph 或 generate_cases")
    requirement_text: str = Field(..., min_length=1, description="需求文档文本内容")
    search_keyword: str = Field(default="", description="图谱检索关键词")

class SubmitTaskResponse(BaseModel):
    """提交任务响应"""
    task_id: str
    status: str = "pending"
    message: str = ""

class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""
    task_id: str
    status: str  # pending / processing / completed / failed
    task_type: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# ==================== 多 Agent 系统模型 ====================

class AgentInfo(BaseModel):
    """Agent 信息"""
    role: str = ""
    name: str = ""
    description: str = ""
    initialized: bool = False

class StepInfo(BaseModel):
    """步骤状态"""
    step_name: str = ""
    status: str = "pending"  # pending / running / completed / failed
    detail: str = ""

class ChatRequest(BaseModel):
    """多 Agent 统一聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID")
    agent_role: Optional[str] = Field(None, description="指定 Agent（不填则自动识别意图）")

class ChatStatusResponse(BaseModel):
    """聊天任务状态响应"""
    task_id: str
    status: str
    task_type: str = "chat"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # processing 状态时的实时进度（steps + agent_chain）
    progress: Optional[Dict[str, Any]] = None