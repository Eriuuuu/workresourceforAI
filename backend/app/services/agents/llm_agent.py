"""
独立大模型 Agent — 通用对话，直接调用 LLM 回答
"""
import time
from loguru import logger

from app.services.agents.base import (
    BaseAgent, AgentRole, AgentResult, AgentContext,
    StepStatus,
)


class LlmAgent(BaseAgent):
    """
    独立大模型 Agent

    直接使用 LLM 处理通用问题，不依赖知识库。
    作为兜底 Agent 处理意图识别无法匹配到专用 Agent 的请求。
    """

    role = AgentRole.LLM
    name = "通用问答"
    description = "独立大模型，处理通用问答和对话"

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.time()
        logger.info(f"[{self.name}] 处理问题: {context.user_message[:100]}")

        step = StepStatus(
            step_name="大模型推理",
            status="running",
            detail="正在调用大模型生成回答...",
        )
        context.steps.append(step)

        try:
            from app.services.agents.llm_client import get_llm_client

            llm = get_llm_client()
            result = await llm.ask(
                question=context.user_message,
                system_message="你是一个智能助手，可以回答各种问题。请给出准确、有用的回答。",
            )

            elapsed = time.time() - start

            if result.get("success"):
                step.status = "completed"
                step.detail = f"生成完成，耗时 {elapsed:.1f}s"
                context.agent_chain.append({
                    "role": self.role.value,
                    "name": self.name,
                    "status": "completed",
                })

                return AgentResult(
                    success=True,
                    answer=result.get("answer", ""),
                    agent_role=self.role.value,
                    agent_name=self.name,
                    processing_time=elapsed,
                    meta={"source": "llm"},
                    steps=context.steps,
                )
            else:
                step.status = "failed"
                step.detail = result.get("error", "大模型返回失败")
                return AgentResult(
                    success=False,
                    answer="大模型处理失败，请重试。",
                    agent_role=self.role.value,
                    agent_name=self.name,
                    processing_time=elapsed,
                    error=result.get("error"),
                    steps=context.steps,
                )

        except Exception as e:
            logger.error(f"[{self.name}] 处理失败: {e}", exc_info=True)
            step.status = "failed"
            step.detail = str(e)

            context.agent_chain.append({
                "role": self.role.value,
                "name": self.name,
                "status": "failed",
            })

            return AgentResult(
                success=False,
                answer=f"处理失败: {str(e)}",
                agent_role=self.role.value,
                agent_name=self.name,
                processing_time=time.time() - start,
                error=str(e),
                steps=context.steps,
            )
