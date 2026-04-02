#向量存储管理器
import os
# import chromadb
# from chromadb.config import Settings
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.schema import Document
from typing import List, Dict, Any
from loguru import logger
import requests


class CustomEmbeddingFunction(Embeddings):
    def __init__(self, embeddings_url: str,api_token: str = None, model: str = "bge-m3"):
        self.embeddings_url = embeddings_url
        self.model = model
        self.api_token = api_token
        self.session = requests.Session()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = self.api_token

        embeddings = []
        for text in texts:
            # 调用您的向量化接口
            response = requests.post(
                self.embeddings_url,
                headers=headers,
                json={
                    "input": [text],
                    "model": self.model
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                # 提取向量数据
                embedding = result["data"][0]["embedding"]
                embeddings.append(embedding)
            else:
                raise Exception(f"向量化请求失败: {response.status_code}, {response.text}")
        
        return embeddings
    def embed_query(self, text: str) -> List[float]:
        """单个查询文本向量化"""
        return self.embed_documents([text])[0]



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
                self.vector_store.add_documents(batch[0:2])
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