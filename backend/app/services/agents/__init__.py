"""
多 Agent 系统

提供 Agent 注册、初始化和调度能力。

层次结构：
  agents/
    base.py           — 基类、数据模型、注册中心
    intent_router.py  — 意图识别与补全（入口 Agent）
    qa_agent.py       — GBMP 智能问答（多轮 RAG）
    llm_agent.py      — 通用 LLM 问答（兜底）
    modeling_agent.py — 智能建模（5 步流水线）
    llm_client.py     — 轻量异步 LLM 客户端（httpx）
"""
from app.services.agents.base import get_registry, AgentRegistry
from app.services.agents.intent_router import IntentRouterAgent
from app.services.agents.qa_agent import GbmpQaAgent
from app.services.agents.llm_agent import LlmAgent
from app.services.agents.modeling_agent import ModelingAgent


def setup_agents() -> AgentRegistry:
    """
    注册所有 Agent（服务启动时调用）

    执行顺序：意图路由 → QA / LLM / 建模（按需调度）
    """
    registry = get_registry()

    # 按顺序注册
    registry.register(GbmpQaAgent())       # 需要单独 init() 加载索引
    registry.register(LlmAgent())          # 即用型，无需额外初始化
    registry.register(ModelingAgent())     # 即用型
    registry.register(IntentRouterAgent()) # 入口路由器（最后注册）

    return registry
