#向量存储管理器
import os
import time as _time
from langchain.vectorstores import Chroma
from langchain.embeddings.base import Embeddings
from langchain.schema import Document
from typing import List, Dict, Any, Optional
from loguru import logger
import requests


class CustomEmbeddingFunction(Embeddings):
    def __init__(self, embeddings_url: str, api_token: str = None, model: str = "bge-m3",
                 batch_size: int = 5, batch_timeout: int = 60, single_timeout: int = 30,
                 max_retries: int = 3, retry_backoff: float = 2.0):
        self.embeddings_url = embeddings_url
        self.model = model
        self.api_token = api_token
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.single_timeout = single_timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    def _do_post(self, texts: List[str], headers: dict, timeout: int) -> requests.Response:
        return requests.post(
            self.embeddings_url, headers=headers,
            json={"input": texts, "model": self.model},
            timeout=timeout,
        )

    def _request_with_retry(self, texts: List[str], headers: dict, timeout: int,
                            label: str) -> Optional[List[List[float]]]:
        """带重试 + 指数退避的请求"""
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._do_post(texts, headers, timeout)
                if resp.status_code == 200:
                    return [item["embedding"] for item in resp.json()["data"]]
                logger.warning(f"{label} status={resp.status_code} (attempt {attempt}/{self.max_retries})")
            except requests.exceptions.Timeout:
                logger.warning(f"{label} 超时 timeout={timeout}s (attempt {attempt}/{self.max_retries})")
            except Exception as e:
                logger.warning(f"{label} 异常: {e} (attempt {attempt}/{self.max_retries})")
            if attempt < self.max_retries:
                wait = self.retry_backoff * (2 ** (attempt - 1))
                logger.info(f"  {label} 等待 {wait:.1f}s 后重试...")
                _time.sleep(wait)
        return None

    def _fallback_single(self, text: str, headers: dict, index: int) -> Optional[List[float]]:
        """单条请求降级（带重试），返回 None 表示彻底失败"""
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._do_post([text], headers, self.single_timeout)
                if resp.status_code == 200:
                    return resp.json()["data"][0]["embedding"]
                logger.warning(f"  单条[{index}] status={resp.status_code} (attempt {attempt})")
            except requests.exceptions.Timeout:
                logger.warning(f"  单条[{index}] 超时 (attempt {attempt})")
            except Exception as e:
                logger.warning(f"  单条[{index}] 异常: {e} (attempt {attempt})")
            if attempt < self.max_retries:
                _time.sleep(self.retry_backoff * (2 ** (attempt - 1)))
        return None

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化 — 重试 + 指数退避 + 自动降级"""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = self.api_token

        # 按索引写入，保证顺序对齐
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        failed_indices: List[int] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            label = f"批量[{i // self.batch_size + 1}](文本 {i}-{i + len(batch) - 1})"

            # 1. 尝试批量请求（带重试）
            result = self._request_with_retry(batch, headers, self.batch_timeout, label)
            if result is not None:
                for j, emb in enumerate(result):
                    embeddings[i + j] = emb
                continue

            # 2. 批量全部失败，降级为逐条
            logger.warning(f"{label} 批量请求全部失败，降级为逐条请求")
            for j, text in enumerate(batch):
                single_emb = self._fallback_single(text, headers, i + j)
                if single_emb is not None:
                    embeddings[i + j] = single_emb
                else:
                    failed_indices.append(i + j)

        # 3. 检查彻底失败的数量
        if failed_indices:
            logger.error(f"嵌入彻底失败 {len(failed_indices)}/{len(texts)} 条，索引: {failed_indices}")
            # 用零向量占位，不中断整体流程（bge-m3 维度 1024）
            for idx in failed_indices:
                embeddings[idx] = [0.0] * 1024

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """单个查询文本向量化（直接单条请求，不走批量逻辑）"""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = self.api_token
        result = self._fallback_single(text, headers, 0)
        if result is None:
            raise Exception("查询文本嵌入失败")
        return result



class LangChainVectorStore():
    """基于LangChain的向量存储管理器"""
    
    def __init__(self, persist_directory: str, api_token :str, embeddings_url: str):
        self.persist_directory = persist_directory
        self.embeddings_url = embeddings_url
        self.api_token= api_token
        self.vector_store = None
        self.embeddings = None
    
    def initialize(self):
        """初始化向量存储"""
        logger.info("初始化向量存储...")
        
        # 创建持久化目录
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # 初始化嵌入模型
        self.embeddings = CustomEmbeddingFunction(
            embeddings_url=self.embeddings_url,
            api_token= self.api_token,
            model="bge-m3"
        )
        
        # 初始化Chroma向量存储
        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
            collection_name="glodon_cpp_code_docs"
        )
        
        logger.info("✓ 向量存储初始化完成")
    
    def add_documents(self, documents: List[Document]):
        """添加文档到向量存储"""
        if not self.vector_store:
            raise ValueError("向量存储未初始化")
        
        logger.info(f"添加 {len(documents)} 个文档到向量存储...")
        
        # 分批处理大文档集
        batch_size = 100
        total_batches = (len(documents) + batch_size - 1) // batch_size
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            try:
                self.vector_store.add_documents(batch)
                logger.info(f"  批次 {batch_num}/{total_batches} 完成")
            except Exception as e:
                logger.error(f"批次 {batch_num} 添加失败: {e}")
                # 继续处理下一批
        
        # 持久化
        self.vector_store.persist()
        
        logger.info("✓ 文档添加完成")
    
    def semantic_search(self, query: str, k: int = 10, filter_dict: Dict = None) -> List[Document]:
        """语义搜索"""
        if not self.vector_store:
            return []
        
        try:
            if filter_dict:
                results = self.vector_store.similarity_search(
                    query, k=k, filter=filter_dict
                )
            else:
                results = self.vector_store.similarity_search(query, k=k)
            
            return results
        
        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            return []
    
    def similarity_search_with_score(self, query: str, k: int = 10) -> List[tuple]:
        """带分数的语义搜索"""
        if not self.vector_store:
            return []
        
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            return results
        except Exception as e:
            logger.error(f"带分数搜索失败: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        if not self.vector_store:
            return {}
        
        try:
            # 直接访问Chroma客户端
            chroma_client = self.vector_store._client
            collection = chroma_client.get_collection("glodon_cpp_code_docs")
            
            count = collection.count()
            metadata_distribution = {}
            
            # 获取一些元数据统计
            results = collection.get(limit=min(1000, count))
            if results['metadatas']:
                for metadata in results['metadatas']:
                    source_type = metadata.get('source_type', 'unknown')
                    metadata_distribution[source_type] = metadata_distribution.get(source_type, 0) + 1
            
            return {
                'total_documents': count,
                'metadata_distribution': metadata_distribution,
                'persist_directory': self.persist_directory
            }
        
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def delete_collection(self):
        """删除集合"""
        if self.vector_store:
            try:
                self.vector_store.delete_collection()
                logger.info("向量集合已删除")
            except Exception as e:
                logger.error(f"删除集合失败: {e}")