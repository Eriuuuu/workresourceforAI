"""
Agent 系统专用轻量 LLM 客户端。

通过 httpx 异步调用 Glodon AI API，不依赖 LangChain 和用例生成系统。
"""
import json
import httpx
from typing import Dict, Any, Optional
from loguru import logger


class AgentLLMClient:
    """轻量 LLM 客户端，仅供 Agent 系统使用（异步）"""

    def __init__(self):
        self._base_url: str = ""
        self._model: str = ""
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None

    def _ensure_initialized(self):
        """延迟初始化：首次调用时读取配置和 token"""
        if self._base_url:
            return
        from app.core.config_for_ai_service import get_config_manager
        from app.core.glodon_api_token import get_glodon_token

        config = get_config_manager()
        self._base_url = config.api.glodonai_llm_url
        self._model = config.api.glodonai_llm_model
        self._token = get_glodon_token()
        # 创建可复用的异步 HTTP 客户端，超时设为 300s
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30))
        logger.info(f"[AgentLLM] 初始化完成: model={self._model}")

    async def ask(self, question: str, system_message: str = "你是一个智能助手。",
                  temperature: float = 0.5, max_tokens: int = 8000) -> Dict[str, Any]:
        """
        异步调用 LLM 生成回答。

        返回格式与 GlodonBaseLLM.ask_question 兼容：
          {"success": True/False, "answer": "...", "error": "..."}
        """
        self._ensure_initialized()

        try:
            payload = json.dumps({
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": str(question)},
                ],
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.8,
                "top_k": 50,
                "repetition_penalty": 1.05,
            })

            headers = {
                "Authorization": self._token,
                "Content-Type": "application/json",
            }

            logger.debug(f"[AgentLLM] 调用 API: {self._base_url}")
            response = await self._client.post(self._base_url, headers=headers, data=payload)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                answer = result["choices"][0]["message"]["content"]
                return {"success": True, "answer": answer}
            else:
                return {"success": False, "error": f"API 响应格式异常: {result}"}

        except Exception as e:
            logger.error(f"[AgentLLM] 调用失败: {e}")
            return {"success": False, "error": str(e)}

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


# 模块级单例
_llm_client: Optional[AgentLLMClient] = None


def get_llm_client() -> AgentLLMClient:
    """获取 Agent LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = AgentLLMClient()
    return _llm_client
