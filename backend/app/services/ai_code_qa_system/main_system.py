import os
import time
from datetime import datetime
from typing import Dict, Any
import json
from loguru import logger

# 导入自定义模块
from app.core.config_for_ai_service import get_settings, get_config_manager
from app.services.ai_code_qa_system.document_processor import CppDocumentProcessor
from app.services.ai_code_qa_system.vector_store import LangChainVectorStore
from app.services.ai_code_qa_system.graph_store import GraphDatabaseManager
from app.services.ai_code_qa_system.code_parser import HybridCppCodeParser,CppCallGraphAnalyzer
from app.services.ai_code_qa_system.code_reader import DynamicCodeReader
from app.services.ai_code_qa_system.retrieval_system import HybridRetrievalSystem
from app.services.ai_code_qa_system.qa_system import CodeAwareQASystem,GlodonBaseLLM
from app.services.ai_code_qa_system.glodon_api_token import get_glodon_token


class LangChainCodeQASystem:
    """基于LangChain的代码问答系统 - 主系统集成"""
    
    def __init__(self, config):
        self.config = config
        
        # 初始化组件
        self.document_processor = None
        self.vector_store = None
        self.graph_store = None
        self.code_parser = None
        self.code_reader = None
        self.retrieval_system = None
        self.qa_system = None
        
        # 系统状态
        self.is_initialized = False
        self.initialization_time = None
        self.system_stats = {}
    
    def initialize(self, force_rebuild: bool = True):
        """初始化系统"""
        logger.info("🚀 初始化基于LangChain的代码问答系统...")
        start_time = time.time()
        
        try:
            # 验证配置
            self.config.validate()
            
            # 初始化组件
            self.document_processor = CppDocumentProcessor(
                self.config.system.codebase_path,
                chunk_size=self.config.system.chunk_size,
                chunk_overlap=self.config.system.chunk_overlap
            )
            
            self.vector_store = LangChainVectorStore(
                self.config.db.chroma_persist_dir,
                get_glodon_token(),
                embeddings_url=self.config.api.glodonai_embedding_url
            )
            self.vector_store.initialize()
            
            self.graph_store = GraphDatabaseManager(
                self.config.db.neo4j_uri,
                self.config.db.neo4j_username,
                self.config.db.neo4j_password
            )
            
            self.code_parser = HybridCppCodeParser(self.config.system.codebase_path)
            self.code_reader = DynamicCodeReader(self.config.system.codebase_path)
            
            # 初始化数据库
            self.graph_store.initialize_database()
            
            # 检查是否需要重建索引
            need_rebuild = force_rebuild or self._need_rebuild_index()
            if need_rebuild:
                logger.info("构建代码索引...")
                
                # 构建向量数据库索引
                logger.info("步骤 1/2: 构建向量数据库索引")
                documents = self.document_processor.load_code_documents()
                self.vector_store.add_documents(documents)
                
                # 构建图数据库索引
                logger.info("步骤 2/2: 构建图数据库索引")
                entities = self.code_parser.parse_codebase_entities()
                print(json.dumps(entities, ensure_ascii=False, indent=2))
                graph_stats = self.graph_store.build_code_graph(entities)
                
                self.system_stats.update({
                    'index_built': True,
                    'index_time': datetime.now().isoformat(),
                    'document_count': len(documents),
                    'entity_count': len(entities),
                    'graph_stats': graph_stats
                })
                
                logger.info("✓ 代码索引构建完成")
            else:
                logger.info("使用现有代码索引")
                self.system_stats['index_built'] = False
            
            # 初始化检索系统
            self.retrieval_system = HybridRetrievalSystem(
                self.vector_store.vector_store,
                self.graph_store,
                self.code_reader
            )
            
            # 初始化QA系统
            self.qa_system = CodeAwareQASystem(
                self.config,
                self.vector_store.vector_store,
                get_glodon_token(),
                self.retrieval_system
            )
            
            self.is_initialized = True
            self.initialization_time = datetime.now()
            
            elapsed = time.time() - start_time
            logger.info(f"✅ 系统初始化完成! 耗时: {elapsed:.2f}秒")
            
            # 显示系统信息
            self._print_system_info()
            
        except Exception as e:
            logger.error(f"❌ 系统初始化失败: {e}")
            raise
    
    def _need_rebuild_index(self) -> bool:
        """检查是否需要重建索引"""
        # 检查向量数据库是否为空
        vector_stats = self.vector_store.get_collection_stats()
        if vector_stats.get('total_documents', 0) == 0:
            return True
        
        # 检查图数据库是否为空
        graph_stats = self.graph_store.get_graph_statistics()
        if graph_stats.get('node_count', 0) == 0:
            return True
        
        return False
    
    def _print_system_info(self):
        """打印系统信息"""
        logger.info("\n" + "="*60)
        logger.info("系统信息")
        logger.info("="*60)
        
        # 代码库信息
        codebase_info = self.code_reader.get_codebase_info()
        logger.info(f"代码库: {codebase_info['codebase_path']}")
        logger.info(f"文件数量: {codebase_info['total_files']}")
        logger.info(f"总大小: {codebase_info['total_size_mb']} MB")
        
        # 向量数据库统计
        vector_stats = self.vector_store.get_collection_stats()
        logger.info(f"向量数据库: {vector_stats.get('total_documents', 0)} 个文档")
        
        # 图数据库统计
        graph_stats = self.graph_store.get_graph_statistics()
        logger.info(f"图数据库: {graph_stats.get('node_count', 0)} 个节点, {graph_stats.get('relationship_count', 0)} 个关系")
        
        logger.info(f"初始化时间: {self.initialization_time}")
        logger.info("="*60 + "\n")
    
    def ask_question(self, question: str) -> Dict[str, Any]:
        """提问并获取答案"""
        if not self.is_initialized:
            self.initialize()
        
        logger.info(f"\n💬 处理问题: {question}")
        start_time = time.time()
        
        try:
            result = self.qa_system.ask_question(question)
            result['processing_time'] = time.time() - start_time
            
            if result['success']:
                logger.info(f"✅ 回答生成成功，参考 {result['files_count']} 个文件")
            else:
                logger.error(f"❌ 回答生成失败: {result['error']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 提问过程出错: {e}")
            return {
                'success': False,
                'question': question,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        vector_stats = self.vector_store.get_collection_stats() if self.vector_store else {}
        graph_stats = self.graph_store.get_graph_statistics() if self.graph_store else {}
        codebase_info = self.code_reader.get_codebase_info() if self.code_reader else {}
        
        status = {
            'initialized': self.is_initialized,
            'initialization_time': self.initialization_time.isoformat() if self.initialization_time else None,
            'codebase': codebase_info,
            'vector_database': vector_stats,
            'graph_database': graph_stats,
            'config': self.config.to_dict()
        }
        
        if self.qa_system:
            status['conversation_history_count'] = len(self.qa_system.get_conversation_history())
        
        return status
    
    def clear_conversation_history(self):
        """清空对话历史"""
        if self.qa_system:
            self.qa_system.clear_memory()
            logger.info("✓ 对话历史已清空")
    
    def debug_retrieval(self, question: str) -> Dict[str, Any]:
        """调试检索过程"""
        if not self.is_initialized:
            self.initialize()
        
        return self.retrieval_system.debug_retrieval(question)
    
    def rebuild_index(self):
        """重建索引"""
        logger.info("开始重建索引...")
        self.initialize(force_rebuild=True)
        logger.info("✓ 索引重建完成")



class GlodonTestcasesGenerater:
    """测试用例辅助生成系统 - 主系统集成"""
    
    def __init__(self, config):
        self.config = config
        self.llm_system = None
        self.is_initialized = False
        

    def initialize(self):
        self.config.validate()
        self.llm_system = GlodonBaseLLM(
            self.config,
            get_glodon_token()
        )
        self.is_initialized = True


    def ask_llm_question(self,question:str) -> Dict[str,Any]:
        if not self.is_initialized:
            self.initialize()

        result = self.llm_system.ask_question(question)
        return result

