from langchain.vectorstores import VectorStore
from langchain.schema import Document
from typing import List, Dict, Any, Optional
import re
from loguru import logger

class HybridRetrievalSystem:
    """混合检索系统 - 结合语义搜索和结构搜索"""
    
    def __init__(self, vector_store: VectorStore, graph_store, code_reader):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.code_reader = code_reader
    
    def retrieve_relevant_code(self, question: str, max_files: int = 5) -> List[Dict[str, Any]]:
        """检索与问题相关的代码"""
        logger.info(f"🔍 检索相关代码: {question}")
        
        # 分析查询意图
        intent = self._analyze_query_intent(question)
        logger.info(f"分析意图: {intent}")
        
        # 执行混合检索
        semantic_results = self._semantic_retrieval(question, intent)
        structural_results = self._structural_retrieval(question, intent)
        
        # 合并和去重结果
        all_files = set()
        file_scores = {}
        
        # 添加语义搜索结果
        for doc in semantic_results:
            file_path = doc.metadata.get('file_path')
            if file_path and file_path not in all_files:
                all_files.add(file_path)
                file_scores[file_path] = 0.8  # 语义搜索默认分数
        
        # 添加结构搜索结果
        for result in structural_results:
            file_path = result.get('file_path')
            if file_path and file_path not in all_files:
                all_files.add(file_path)
                file_scores[file_path] = 0.9  # 结构搜索分数更高
            elif file_path:
                file_scores[file_path] = max(file_scores.get(file_path, 0), 0.9)
        
        # 按分数排序
        sorted_files = sorted(all_files, key=lambda x: file_scores.get(x, 0), reverse=True)
        file_paths = sorted_files[:max_files]
        
        # 读取完整的代码内容
        code_contexts = []
        for file_path in file_paths:
            full_content = self.code_reader.read_entire_file(file_path)
            if not full_content.startswith('错误:'):
                code_contexts.append({
                    'file_path': file_path,
                    'content': full_content,
                    'retrieval_type': 'hybrid',
                    'confidence': file_scores.get(file_path, 0.5),
                    'metadata': {
                        'file_path': file_path,
                        'search_strategy': intent['strategy'],
                        'score': file_scores.get(file_path, 0.5)
                    }
                })
        
        logger.info(f"✓ 找到 {len(code_contexts)} 个相关代码文件")
        return code_contexts
    
    def _analyze_query_intent(self, question: str) -> Dict[str, Any]:
        """分析查询意图"""
        question_lower = question.lower()
        
        # 检测结构搜索的迹象
        structural_indicators = ['函数', '类', '方法', '调用', '继承', '包含', '定义', '实现',
                                 '接口', '模块', '服务', '组件', '变量', '属性', '配置']
        structural_keywords = [word for word in structural_indicators if word in question_lower]
        
        # 检测具体实体查询（中文模式）
        entity_patterns = [
            r'(\w+)函数',
            r'(\w+)类',
            r'(\w+)方法',
            r'(\w+)的实现',
            r'(\w+)接口',
            r'(\w+)模块',
            r'(\w+)服务',
            r'(\w+)组件',
        ]
        
        entities = []
        for pattern in entity_patterns:
            matches = re.findall(pattern, question)
            entities.extend(matches)
        
        # 提取可能是代码标识符的英文词（驼峰/下划线/帕斯卡命名，长度>=3）
        code_id_matches = re.findall(r'\b([a-zA-Z][a-zA-Z0-9_]{2,})\b', question)
        code_stop_words = {
            'the', 'this', 'that', 'what', 'which', 'who', 'how', 'why', 'when', 'where',
            'and', 'not', 'but', 'for', 'are', 'was', 'were', 'has', 'had', 'does',
            'can', 'will', 'with', 'from', 'also', 'just', 'than', 'then', 'into',
        }
        code_entities = [
            w for w in code_id_matches
            if w.lower() not in code_stop_words
            and (any(c.isupper() for c in w) or '_' in w)
        ]
        entities.extend(code_entities)
        
        if structural_keywords or entities:
            strategy = 'structural_search'
        else:
            strategy = 'semantic_search'
        
        return {
            "strategy": strategy,
            "structural_keywords": structural_keywords,
            "entities": entities,
            "keywords": self._extract_keywords(question)
        }
    
    def _semantic_retrieval(self, question: str, intent: Dict[str, Any]) -> List[Document]:
        """语义检索"""
        try:
            # 使用LangChain的向量存储进行语义搜索
            results = self.vector_store.similarity_search(question, k=10)
            logger.info(f"语义检索找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"语义检索失败: {e}")
            return []
    
    def _structural_retrieval(self, question: str, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """结构检索 - 结合精确匹配与模糊搜索"""
        results = []
        seen_file_entity = set()  # (file_path, entity_name) 去重
        
        # 1. 基于提取的实体名称精确搜索（高优先级）
        for entity in intent['entities']:
            for entity_type in ['Function', 'Class', 'Struct']:
                graph_results = self.graph_store.query_related_entities(entity, entity_type)
                for graph_result in graph_results:
                    if 'file_path' in graph_result and graph_result['file_path']:
                        key = (graph_result['file_path'], graph_result['name'])
                        if key not in seen_file_entity:
                            seen_file_entity.add(key)
                            results.append({
                                'file_path': graph_result['file_path'],
                                'entity_type': entity_type.lower(),
                                'entity_name': graph_result['name'],
                                'signature': graph_result.get('signature', ''),
                                'search_type': 'entity_exact_match'
                            })
        
        # 2. 基于所有提取的关键词进行图数据库模糊搜索
        all_keywords = list(set(intent.get('keywords', []) + intent.get('structural_keywords', [])))
        # 按词长降序排列，优先匹配更具体的关键词
        all_keywords.sort(key=len, reverse=True)
        for keyword in all_keywords[:10]:  # 限制最多查询 10 个关键词，避免过多查询
            graph_results = self.graph_store.search_entities_by_keyword(keyword, limit=10)
            for graph_result in graph_results:
                file_path = graph_result.get('file_path')
                if file_path:
                    key = (file_path, graph_result.get('name', ''))
                    if key not in seen_file_entity:
                        seen_file_entity.add(key)
                        results.append({
                            'file_path': file_path,
                            'entity_type': graph_result.get('type', ''),
                            'entity_name': graph_result.get('name', ''),
                            'signature': graph_result.get('signature', ''),
                            'search_type': 'entity_fuzzy_match',
                            'search_keyword': keyword,
                        })
        
        # 3. 基于结构关键词做向量搜索（补充语义覆盖）
        for keyword in intent['structural_keywords']:
            try:
                keyword_results = self.vector_store.similarity_search(keyword, k=5)
                for doc in keyword_results:
                    file_path = doc.metadata.get('file_path')
                    if file_path:
                        results.append({
                            'file_path': file_path,
                            'search_keyword': keyword,
                            'content_preview': doc.page_content[:200],
                            'search_type': 'keyword_match'
                        })
            except Exception as e:
                logger.error(f"关键词搜索失败: {e}")
        
        logger.info(f"结构检索找到 {len(results)} 个结果 (实体精确匹配 + 关键词模糊图搜索 + 向量补充)")
        return results
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        stop_words = {
            '什么', '怎么', '如何', '为什么', '哪里', '哪个', '哪些', '请问',
            '可以', '能够', '应该', '需要', '想要', '寻找', '查找', '搜索',
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一个', '一种', '一下', '一些', '这个', '那个', '这些', '那些'
        }
        
        words = re.findall(r'[\u4e00-\u9fff\w]+', text.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        
        return keywords
    
    def debug_retrieval(self, question: str) -> Dict[str, Any]:
        """调试检索过程"""
        intent = self._analyze_query_intent(question)
        semantic_results = self._semantic_retrieval(question, intent)
        structural_results = self._structural_retrieval(question, intent)
        
        return {
            'question': question,
            'intent_analysis': intent,
            'semantic_results_count': len(semantic_results),
            'structural_results_count': len(structural_results),
            'semantic_results_preview': [
                {
                    'file_path': doc.metadata.get('file_path'),
                    'content_preview': doc.page_content[:100] + '...' if len(doc.page_content) > 100 else doc.page_content
                }
                for doc in semantic_results[:3]
            ],
            'structural_results_preview': structural_results[:3]
        }