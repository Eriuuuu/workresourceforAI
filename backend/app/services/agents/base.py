"""
多 Agent 框架 - 基类与注册中心
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from loguru import logger


# ==================== 数据模型 ====================

class AgentRole(str, Enum):
    """Agent 角色标识"""
    INTENT_ROUTER = "intent_router"
    GBMP_QA = "gbmp_qa"
    LLM = "llm"
    MODELING = "modeling"


class StepStatus(BaseModel):
    """步骤执行状态"""
    step_name: str = ""
    status: str = "pending"  # pending / running / completed / failed
    detail: str = ""
    created_at: str = ""
    updated_at: str = ""


class AgentMessage(BaseModel):
    """Agent 间通信消息"""
    role: str  # user / assistant / system
    content: str = ""
    agent_name: str = ""
    agent_role: str = ""
    meta: Dict[str, Any] = {}


class AgentContext(BaseModel):
    """Agent 执行上下文（贯穿整个请求链路）"""
    session_id: str = ""
    user_message: str = ""
    # 意图路由补全后的完整意图描述
    enriched_intent: str = ""
    current_agent_role: str = ""
    steps: List[StepStatus] = []
    # 请求链路记录
    agent_chain: List[Dict[str, str]] = []  # [{role, agent_name, status}]
    # 对话历史（用于多轮 RAG）
    conversation_history: List[Dict[str, str]] = []
    # 最终结果
    answer: str = ""
    success: bool = False
    error: str = ""

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data):
        super().__init__(**data)
        # 非 Pydantic 字段：进度回调（由 API 层注入，供 Agent 实时推送进度）
        self._progress_callback = None


class AgentResult(BaseModel):
    """Agent 执行结果"""
    success: bool
    answer: str = ""
    agent_role: str = ""
    agent_name: str = ""
    processing_time: float = 0
    meta: Dict[str, Any] = {}
    steps: List[StepStatus] = []
    error: str = ""


# ==================== Agent 基类 ====================

class BaseAgent(ABC):
    """
    Agent 基类

    所有 Agent 继承此类并实现 execute() 方法。
    支持 init() / destroy() 生命周期，可选择性重写。
    """

    role: AgentRole = AgentRole.LLM
    name: str = ""
    description: str = ""

    def __init__(self):
        self._initialized = False

    def init(self) -> None:
        """初始化 Agent（可选重写，用于加载模型/建立连接等）"""
        self._initialized = True
        logger.info(f"[Agent] {self.name} 初始化完成")

    def destroy(self) -> None:
        """销毁 Agent（可选重写，用于释放资源）"""
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行 Agent 逻辑（异步）

        Args:
            context: 执行上下文，包含用户消息、会话信息、步骤状态等

        Returns:
            AgentResult: 执行结果
        """
        ...


# ==================== Agent 注册中心 ====================

class AgentRegistry:
    """全局 Agent 注册中心（单例）"""

    _instance: Optional["AgentRegistry"] = None
    _agents: Dict[str, BaseAgent] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
        return cls._instance

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.role.value] = agent
        logger.info(f"[Registry] 注册 Agent: {agent.name} ({agent.role.value})")

    def get(self, role: str) -> Optional[BaseAgent]:
        return self._agents.get(role)

    def list_agents(self) -> List[Dict[str, str]]:
        return [
            {"role": a.role.value, "name": a.name, "description": a.description}
            for a in self._agents.values()
        ]

    def is_ready(self, role: str) -> bool:
        agent = self._agents.get(role)
        return agent is not None and agent.is_initialized

    def init_all(self) -> None:
        for agent in self._agents.values():
            if not agent.is_initialized:
                agent.init()

    def destroy_all(self) -> None:
        for agent in self._agents.values():
            agent.destroy()
        self._agents.clear()


def get_registry() -> AgentRegistry:
    return AgentRegistry()
