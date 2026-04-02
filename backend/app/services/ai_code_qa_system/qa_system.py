from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseRetriever
from langchain_core.language_models import BaseChatModel
from langchain.schema.messages import HumanMessage, AIMessage, SystemMessage
from langchain.schema.output import ChatGeneration, ChatResult
from langchain.schema import Document
from typing import List, Dict, Any, Optional, Iterator
import tiktoken
import json
import requests
import base64
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
        """异步生成回复"""
        # 简单实现：调用同步方法
        return self._generate(messages, stop, run_manager, **kwargs)
    
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


class CodeRetriever(BaseRetriever):
    """自定义代码检索器"""
    # 在Pydantic模型中，必须在这里定义所有字段
    vector_store: Any = Field(...)
    retrieval_system: Any = Field(...)
    max_files: int = Field(default=5)
    
    class Config:
        arbitrary_types_allowed = True  # 允许任意类型

    def __init__(self, vector_store, retrieval_system, max_files: int = 5):
        super().__init__(
            vector_store=vector_store,
            retrieval_system=retrieval_system,
            max_files=max_files
        )
    
    def get_relevant_documents(self, query: str) -> List[Document]:
        """获取相关文档"""
        try:
            # 使用混合检索系统获取相关代码文件
            code_contexts = self.retrieval_system.retrieve_relevant_code(query, self.max_files)
            
            # 将代码上下文转换为Document对象
            documents = []
            
            for context in code_contexts:
                # 确保context是字典类型
                if isinstance(context, dict):
                    content = context.get('content', '')
                    metadata = context.get('metadata', {})
                else:
                    content = str(context)
                    metadata = {}
                    
                doc = Document(
                    page_content=content,
                    metadata=metadata
                )
                documents.append(doc)
            
            logger.debug(f"检索到 {len(documents)} 个相关文档")
            return documents
            
        except Exception as e:
            logger.error(f"检索文档失败: {e}")
            return []
    
    async def aget_relevant_documents(self, query: str) -> List[Document]:
        """异步获取相关文档"""
        # 简单实现，直接调用同步方法
        return self.get_relevant_documents(query)


class CodeAwareQASystem:
    """基于LangChain的代码感知问答系统"""
    
    def __init__(self, config, vector_store, api_token, retrieval_system):
        self.config = config
        self.api_token = api_token
        self.vector_store = vector_store
        self.retrieval_system = retrieval_system
        
        logger.info(f"初始化QA系统: api_token长度={len(api_token) if api_token else 0}")
        
        # 确保api_token是字符串
        if not isinstance(api_token, str):
            logger.warning(f"API token不是字符串类型，进行转换: {type(api_token)}")
            api_token = str(api_token)
        
        # 初始化LangChain组件
        self.llm = GlodonAIChatModel(
            model_name=getattr(config.api, 'glodonai_llm_model', 'Arulkqtcfw04k'),
            api_key=api_token,
            temperature=0.1,
            max_tokens=8000,
            use_streaming=False
        )
        
        self.memory = ConversationBufferWindowMemory(
            k=5,
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        # 创建自定义检索器
        max_files = getattr(config.system, 'max_files_per_query', 5)
        self.retriever = CodeRetriever(self.vector_store, self.retrieval_system, max_files)
        
        # 创建提示模板
        self.prompt = self._create_prompt_template()
        
        # 创建QA链
        self.qa_chain = self._create_qa_chain()
        
        # Token计数器
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except:
            # 如果cl100k_base不可用，使用gpt2作为备选
            self.encoding = tiktoken.get_encoding("gpt2")
        
        logger.info("✓ 代码感知问答系统初始化完成")
    
    def _create_prompt_template(self) -> PromptTemplate:
        """创建提示模板"""
        template = """你是一个专业的C++代码专家。基于提供的C++代码文件内容回答问题。

上下文信息:
{context}

对话历史:
{chat_history}

当前问题: {question}

请基于以上代码内容回答以下问题。要求:
1. 仔细分析每个提供的代码文件，理解其结构、功能和实现
2. 直接引用具体的文件路径、函数名、类名
3. 如果代码不完整或需要更多上下文，明确说明需要查看哪些其他文件
4. 提供基于实际代码的具体建议和解释
5. 如果发现代码中的问题、潜在bug或改进点，请明确指出

请用中文回答，确保回答准确、实用，并完全基于提供的真实代码内容。"""

        return PromptTemplate(
            template=template,
            input_variables=["context", "chat_history", "question"]
        )
    
    def _create_qa_chain(self):
        """创建QA链"""
        try:
            qa_chain = ConversationalRetrievalChain.from_llm(
                llm=self.llm,
                retriever=self.retriever,
                memory=self.memory,
                combine_docs_chain_kwargs={"prompt": self.prompt},
                return_source_documents=True,
                verbose=False
            )
            return qa_chain
        except Exception as e:
            logger.error(f"创建QA链失败: {e}")
            raise
    
    def ask_question(self, question: str) -> Dict[str, Any]:
        """提问并获取答案"""
        try:
            logger.info(f"处理问题: {question}")
            
            # 确保问题是字符串
            question_str = str(question)
            
            # 使用LangChain的QA链
            result = self.qa_chain({
                "question": question_str,
                "chat_history": self.memory.chat_memory.messages
            })
            
            # 提取源文档信息
            source_files = []
            if 'source_documents' in result:
                for doc in result['source_documents']:
                    file_path = doc.metadata.get('file_path', '未知')
                    if file_path not in source_files:
                        source_files.append(str(file_path))
            
            # 计算token使用量
            input_tokens = self._count_tokens(question_str + str(result.get('source_documents', [])))
            output_tokens = self._count_tokens(result['answer'])
            
            logger.info(f"✓ 成功生成答案，使用 {len(source_files)} 个源文件")
            
            return {
                'success': True,
                'question': question_str,
                'answer': result['answer'],
                'source_files': source_files,
                'files_count': len(source_files),
                'token_usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"提问失败: {e}", exc_info=True)
            return {
                'success': False,
                'question': str(question) if question else "未知问题",
                'error': str(e)
            }
    
    def _count_tokens(self, text: Any) -> int:
        """计算文本的token数量"""
        if isinstance(text, str):
            return len(self.encoding.encode(text))
        elif isinstance(text, list):
            total = 0
            for item in text:
                if isinstance(item, Document):
                    total += self._count_tokens(item.page_content)
                    total += self._count_tokens(str(item.metadata))
                elif hasattr(item, 'content'):
                    total += self._count_tokens(item.content)
                elif hasattr(item, 'page_content'):
                    total += self._count_tokens(item.page_content)
                else:
                    total += self._count_tokens(str(item))
            return total
        else:
            return len(self.encoding.encode(str(text)))
    
    def clear_memory(self):
        """清空记忆"""
        self.memory.clear()
        logger.info("✓ 对话记忆已清空")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        messages = self.memory.chat_memory.messages
        history = []
        
        for message in messages:
            if isinstance(message, SystemMessage):
                role = "system"
            elif isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                role = "unknown"
            
            history.append({
                'role': role,
                'content': message.content,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return history

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
            model_name=getattr(config.api, 'glodonai_llm_model', 'Arulkqtcfw04k'),
            api_key=api_token,
            temperature=0.1,
            max_tokens=8000,
            use_streaming=False
        )
    def ask_question(self, question:str) -> Dict[str, Any]:

        try:
            logger.info(f"处理问题: {question}")
            question_str = str(question)
            
            # 2. 构建消息列表
            messages = [
                SystemMessage(content="你是一个专业的C++代码分析助手。"),
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
