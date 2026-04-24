from langchain_core.language_models import BaseChatModel
from langchain.schema.messages import HumanMessage, AIMessage, SystemMessage
from langchain.schema.output import ChatGeneration, ChatResult
from typing import List, Dict, Any, Optional
import json
import requests
from loguru import logger
from datetime import datetime
from pydantic import BaseModel, Field
from langchain.callbacks.manager import CallbackManagerForLLMRun


class GlodonAIChatModel(BaseChatModel):
    """Glodon AI聊天模型封装"""
    
    model_name: str = "Arulkqtcfw04k"
    base_url: str = "https://copilot.glodon.com/api/cvforce/aishop/v1/chat/completions"
    api_key: str 
    temperature: float = 0.5
    max_tokens: int = 8000
    top_p: float = 0.8
    top_k: int = 50
    repetition_penalty: float = 1.05
    
    # 使用别名避免与BaseModel的stream方法冲突
    use_streaming: bool = False
    
    class Config:
        # 允许通过别名设置字段
        allow_population_by_field_name = True
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型"""
        return "glodon-ai"


    def _generate(
        self,
        messages: List,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        """生成回复"""
        try:
            # 转换消息格式
            formatted_messages = self._format_messages(messages)
            
            # 构建请求负载 - 直接使用实例属性，它们已经是正确的类型
            payload =json.dumps({
                "model": self.model_name,
                "messages": formatted_messages,
                "stream": self.use_streaming,  # 使用重命名的字段
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "top_k": self.top_k,
                "repetition_penalty": self.repetition_penalty
            })

            # 如果有额外的参数，合并
            # if kwargs:
            #     payload.update(kwargs)

            # 构建请求头
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json'
            }
            
            # 发送请求
            logger.info(f"调用Glodon AI API: {self.base_url}")
            
            response = requests.request("POST",self.base_url,headers=headers,data=payload)
            
            # 检查响应
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"API响应状态码: {response.status_code}")
            logger.info(f"API响应状态码: {result}")
            
            # 提取回复
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                
                # 创建ChatGeneration对象
                generation = ChatGeneration(
                    message=AIMessage(content=content),
                    generation_info=result
                )
                
                return ChatResult(generations=[generation])
            else:
                raise ValueError(f"API响应格式异常: {result}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Glodon AI API请求失败: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            # 打印原始响应内容用于调试
            if 'response' in locals():
                logger.error(f"原始响应: {response.text[:500]}")
            raise
        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            raise
    
    def _format_messages(self, messages: List) -> List[Dict]:
        """将LangChain消息格式转换为Glodon AI格式"""
        formatted_messages = []
        
        for message in messages:
            # 确保消息内容是可序列化的
            if hasattr(message, 'content'):
                content = message.content
            else:
                content = str(message)
            
            if isinstance(message, SystemMessage):
                formatted_messages.append({
                    "role": "system",
                    "content": content
                })
            elif isinstance(message, HumanMessage):
                formatted_messages.append({
                    "role": "user",
                    "content": content
                })
            elif isinstance(message, AIMessage):
                formatted_messages.append({
                    "role": "assistant",
                    "content": content
                })
            else:
                # 尝试其他消息类型
                formatted_messages.append({
                    "role": "user",
                    "content": str(message.content) if hasattr(message, 'content') else str(message)
                })
        
        return formatted_messages
    
    async def _agenerate(
        self,
        messages: List,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        """异步生成回复 - 使用线程池执行同步 HTTP 请求"""
        import asyncio
        return await asyncio.to_thread(self._generate, messages, stop, run_manager, **kwargs)
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """返回识别参数"""
        return {
            "model_name": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "stream": self.use_streaming
        }


class GlodonBaseLLM:
    """glodon大模型"""
    
    def __init__(self, config,api_token):
        self.config = config
        self.api_token = api_token
        
        logger.info(f"初始化LLM: api_token长度={len(api_token) if api_token else 0}")
        
        # 确保api_token是字符串
        if not isinstance(api_token, str):
            logger.warning(f"API token不是字符串类型，进行转换: {type(api_token)}")
            api_token = str(api_token)
        
        # 实例化模型
        self.llm = GlodonAIChatModel(
            model_name=getattr(config.api, 'glodonai_llm_model', 'Azcrc2go7oiyq'),
            api_key=api_token,
            temperature=0.1,
            max_tokens=8000,
            use_streaming=False
        )
    def ask_question(self, question:str, system_message:str) -> Dict[str, Any]:

        try:
            logger.info(f"处理问题: {question}")
            question_str = str(question)
            
            # 2. 构建消息列表
            messages = [
                SystemMessage(content=f"{system_message}"),
                HumanMessage(content=question)
            ]
            # 使用LangChain的QA链
            response  = self.llm.invoke(messages)
            
            logger.info(f"✓ 成功生成答案22")
            print(response)
            print(type(response))
            
            return {
                'success': True,
                'question': question_str,
                'answer': response.content
            }
            
        except Exception as e:
            logger.error(f"提问失败: {e}", exc_info=True)
            return {
                'success': False,
                'question': str(question) if question else "未知问题",
                'error': str(e)
            }


