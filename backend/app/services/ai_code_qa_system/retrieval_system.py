"""
混合检索系统 — 结合语义搜索（向量）和结构搜索（图数据库）

检索策略：
  1. 语义检索：向量数据库 chunk 级匹配，使用分数过滤低质量结果
  2. 结构检索：图数据库实体精确匹配 + 关键词模糊搜索（全类型 + 不区分大小写）
     + 中英文同义词扩展 + 沿 CONTAINS/CALLS 扩展关联实体
  3. 合并去重：chunk 级 + 实体级去重，保留详细信息
  4. 内容读取：读取完整文件内容 + 附带实体摘要信息
"""
from langchain.vectorstores import VectorStore
from langchain.schema import Document
from typing import List, Dict, Any, Set, Tuple
import re
from loguru import logger


# 中英文同义词映射，用于增强检索
_ZH_EN_SYNONYMS = {
    # 通用开发术语
    "导出": ["export", "exportar"],
    "导入": ["import", "importar"],
    "导入导出": ["import", "export"],
    "画": ["draw", "render", "paint", "create"],
    "绘制": ["draw", "render", "plot", "paint"],
    "创建": ["create", "new", "make", "build", "generate"],
    "删除": ["delete", "remove", "destroy", "erase"],
    "修改": ["modify", "change", "update", "edit", "alter"],
    "获取": ["get", "fetch", "obtain", "acquire", "retrieve"],
    "设置": ["set", "config", "configure", "setup"],
    "初始化": ["init", "initialize", "setup", "construct"],
    "保存": ["save", "store", "persist", "write"],
    "读取": ["read", "load", "fetch", "get"],
    "加载": ["load", "read", "import"],
    "函数": ["function", "method", "func", "procedure"],
    "方法": ["method", "function", "func"],
    "类": ["class", "type", "struct"],
    "结构体": ["struct", "structure"],
    "接口": ["interface", "api"],
    "配置": ["config", "configuration", "setting", "option"],
    "错误": ["error", "exception", "fail", "fault"],
    "异常": ["exception", "error", "fault"],
    "测试": ["test", "testing", "unittest"],
    "建模": ["modeling", "model", "build", "construct"],
    "参数": ["param", "parameter", "argument", "args"],
    "返回": ["return", "output", "result"],
    "处理": ["process", "handle", "manage", "deal"],
    "调用": ["call", "invoke", "execute", "run"],
    "实现": ["implement", "realize", "fulfill"],
    "定义": ["define", "declare", "specify"],
    "继承": ["inherit", "extend", "derive"],
    "包含": ["contain", "include", "has"],
    "遍历": ["traverse", "iterate", "walk"],
    "转换": ["convert", "transform", "cast", "translate"],
    "解析": ["parse", "resolve", "analyze"],
    "生成": ["generate", "create", "produce", "build"],
    "校验": ["validate", "verify", "check"],
    "注册": ["register", "reg", "bind"],
    "注销": ["unregister", "unreg", "unbind", "destroy"],
}


class HybridRetrievalSystem:
    """混合检索系统 - 结合语义搜索和结构搜索"""

    def __init__(self, vector_store: VectorStore, graph_store, code_reader):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.code_reader = code_reader

    def retrieve_relevant_code(self, question: str, max_files: int = 5) -> List[Dict[str, Any]]:
        """检索与问题相关的代码（chunk 级 + 关系扩展 + 分数过滤）"""
        logger.info(f"检索相关代码: {question}")

        intent = self._analyze_query_intent(question)
        logger.info(f"分析意图: strategy={intent['strategy']}, entities={intent['entities']}, keywords={intent['keywords']}")

        # ---- 阶段1：语义检索（chunk 级 + 分数过滤） ----
        semantic_results = self._semantic_retrieval(question, intent)

        # ---- 阶段2：结构检索（实体级 + 关系扩展 + 全类型 + 模糊） ----
        structural_results = self._structural_retrieval(question, intent)

        # ---- 阶段3：合并去重 ----
        file_map: Dict[str, Dict[str, Any]] = {}

        for doc in semantic_results:
            file_path = doc.metadata.get("file_path", "")
            if not file_path:
                continue
            score = doc.metadata.get("_score", 0.8)
            if file_path not in file_map:
                file_map[file_path] = {"score": 0.0, "chunks": [], "entities": []}
            file_map[file_path]["chunks"].append({
                "content": doc.page_content[:1000],
                "metadata": doc.metadata,
                "score": score,
            })
            file_map[file_path]["score"] = max(file_map[file_path]["score"], score)

        for result in structural_results:
            file_path = result.get("file_path", "")
            if not file_path:
                continue
            stype = result.get("search_type", "")
            score = 0.95 if "exact" in stype else (0.85 if "fuzzy" in stype else 0.7)
            if file_path not in file_map:
                file_map[file_path] = {"score": 0.0, "chunks": [], "entities": []}
            entity_info = {
                "name": result.get("entity_name", ""),
                "type": result.get("entity_type", ""),
                "signature": result.get("signature", ""),
                "search_type": stype,
                "line_start": result.get("line_start"),
                "line_end": result.get("line_end"),
                "parameters": result.get("parameters_text"),
                "return_type": result.get("return_type"),
            }
            if entity_info["name"] and entity_info not in file_map[file_path]["entities"]:
                file_map[file_path]["entities"].append(entity_info)
            file_map[file_path]["score"] = max(file_map[file_path]["score"], score)

        # ---- 阶段4：按分数排序，读取文件内容 ----
        sorted_files = sorted(file_map.keys(), key=lambda x: file_map[x]["score"], reverse=True)
        file_paths = sorted_files[:max_files]

        code_contexts = []
        for file_path in file_paths:
            info = file_map[file_path]
            full_content = self.code_reader.read_entire_file(file_path)

            if full_content.startswith("错误:"):
                continue

            entity_summary = self._build_entity_summary(info["entities"])

            code_contexts.append({
                "file_path": file_path,
                "content": full_content,
                "retrieval_type": "hybrid",
                "confidence": info["score"],
                "entity_summary": entity_summary,
                "matched_chunks": info["chunks"][:3],
                "metadata": {
                    "file_path": file_path,
                    "search_strategy": intent["strategy"],
                    "score": info["score"],
                },
            })

        logger.info(f"找到 {len(code_contexts)} 个相关代码文件 (共检索到 {len(file_map)} 个)")
        return code_contexts

    def _build_entity_summary(self, entities: List[Dict[str, Any]]) -> str:
        """构建实体摘要信息，供 LLM 理解文件结构"""
        if not entities:
            return ""

        lines = []
        seen = set()
        for e in entities:
            name = e.get("name", "")
            if name in seen:
                continue
            seen.add(name)
            etype = e.get("type", "")
            sig = e.get("signature", "")
            params = e.get("parameters", "")
            ret = e.get("return_type", "")
            line_start = e.get("line_start")
            line_end = e.get("line_end")

            detail = f"[{etype}] {name}"
            if ret:
                detail += f" → {ret}"
            if params:
                detail += f"({params})"
            if sig and len(sig) > len(detail):
                detail = f"[{etype}] {name}: {sig[:200]}"
            if line_start and line_end:
                detail += f" [L{line_start}-{line_end}]"

            lines.append(f"  - {detail}")

        return "文件中包含的实体:\n" + "\n".join(lines) if lines else ""

    # ==================== 语义检索（chunk 级 + 分数过滤） ====================

    def _semantic_retrieval(self, question: str, intent: Dict[str, Any]) -> List[Document]:
        """语义检索 — 使用带分数的搜索，过滤低质量结果"""
        _ = intent
        try:
            # 优先使用带分数的搜索
            scored_results = self.vector_store.similarity_search_with_score(question, k=20)
            logger.info(f"语义检索: 获取 {len(scored_results)} 个 chunk（带分数）")

            # 过滤低质量结果：分数阈值（距离越小越好，Chroma 使用 L2 距离）
            filtered = []
            for doc, score in scored_results:
                # Chroma L2 距离：通常 < 1.5 为相关，< 1.0 为高度相关
                if score < 2.0:
                    doc.metadata["_score"] = round(max(0.0, 1.0 - score / 2.0), 3)
                    filtered.append(doc)
                else:
                    # 仍然保留但标记低分
                    doc.metadata["_score"] = 0.3
                    filtered.append(doc)

            # 只取前 15 个
            filtered.sort(key=lambda d: d.metadata.get("_score", 0), reverse=True)
            logger.info(f"语义检索: 过滤后保留 {len(filtered)} 个 chunk")
            return filtered[:15]

        except Exception as e:
            logger.error(f"带分数搜索失败，回退到普通搜索: {e}")
            try:
                results = self.vector_store.similarity_search(question, k=15)
                for doc in results:
                    doc.metadata["_score"] = 0.7
                return results
            except Exception as e2:
                logger.error(f"语义检索失败: {e2}")
                return []

    # ==================== 结构检索（全类型 + 模糊 + 关系扩展） ====================

    def _structural_retrieval(self, question: str, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """结构检索 — 实体精确匹配 + 模糊搜索 + 同义词扩展 + 关系扩展"""
        _ = question
        all_results: List[Dict[str, Any]] = []
        seen_file_entity: Set[Tuple[str, str]] = set()

        # 1. 实体精确匹配（全类型：Function/Class/Struct/Namespace/Enum）
        entity_types = ["Function", "Class", "Struct", "Namespace", "Enum"]
        for entity in intent["entities"]:
            for entity_type in entity_types:
                graph_results = self.graph_store.query_related_entities(entity, entity_type)
                for r in graph_results:
                    fp = r.get("file_path", "") or r.get("file_path_src", "")
                    name = r.get("name", "")
                    if fp and name and (fp, name) not in seen_file_entity:
                        seen_file_entity.add((fp, name))
                        all_results.append({
                            "file_path": fp,
                            "entity_type": entity_type.lower(),
                            "entity_name": name,
                            "signature": r.get("signature", ""),
                            "line_start": r.get("line_start"),
                            "line_end": r.get("line_end"),
                            "parameters_text": r.get("parameters_text", ""),
                            "return_type": r.get("return_type", ""),
                            "search_type": "entity_exact_match",
                        })
                        # 沿 CONTAINS 关系扩展：查找同文件中的其他实体
                        related = self._expand_file_entities(fp, exclude={(fp, name)})
                        for rel in related:
                            key = (rel.get("file_path", ""), rel.get("entity_name", ""))
                            if key not in seen_file_entity:
                                seen_file_entity.add(key)
                                all_results.append(rel)

            # 对精确匹配的实体沿 CALLS/CONTAINS 扩展关联实体
            try:
                expanded = self.graph_store.expand_entity_relations(entity, "Function", depth=1)
                for exp in expanded:
                    fp = exp.get("file_path", "")
                    name = exp.get("entity_name", "")
                    if fp and name and (fp, name) not in seen_file_entity:
                        seen_file_entity.add((fp, name))
                        all_results.append({
                            "file_path": fp,
                            "entity_type": exp.get("entity_type", ""),
                            "entity_name": name,
                            "signature": exp.get("signature", ""),
                            "search_type": "relation_expand_calls",
                        })
            except Exception as e:
                logger.debug(f"关系扩展失败: {e}")

        # 2. 关键词模糊图搜索（原始关键词 + 同义词扩展）
        all_keywords = list(set(intent.get("keywords", []) + intent.get("structural_keywords", [])))
        # 添加同义词扩展
        expanded_keywords = self._expand_synonyms(all_keywords)
        all_keywords = list(set(all_keywords + expanded_keywords))
        all_keywords.sort(key=len, reverse=True)

        for keyword in all_keywords[:15]:
            if len(keyword) < 2:
                continue
            graph_results = self.graph_store.search_entities_by_keyword(keyword, limit=10)
            for r in graph_results:
                fp = r.get("file_path")
                name = r.get("name", "")
                if fp and name and (fp, name) not in seen_file_entity:
                    seen_file_entity.add((fp, name))
                    all_results.append({
                        "file_path": fp,
                        "entity_type": r.get("type", ""),
                        "entity_name": name,
                        "signature": r.get("signature", ""),
                        "line_start": r.get("line_start"),
                        "line_end": r.get("line_end"),
                        "parameters_text": r.get("parameters_text", ""),
                        "return_type": r.get("return_type", ""),
                        "search_type": "entity_fuzzy_match",
                        "search_keyword": keyword,
                    })

        # 3. 结构关键词向量补充
        search_terms = list(set(intent.get("structural_keywords", []) + intent.get("entities", [])))
        for keyword in search_terms[:5]:
            try:
                keyword_results = self.vector_store.similarity_search(keyword, k=5)
                for doc in keyword_results:
                    fp = doc.metadata.get("file_path")
                    if fp:
                        all_results.append({
                            "file_path": fp,
                            "search_keyword": keyword,
                            "content_preview": doc.page_content[:200],
                            "search_type": "keyword_vector_supplement",
                        })
            except Exception as e:
                logger.error(f"关键词向量搜索失败: {e}")

        logger.info(f"结构检索找到 {len(all_results)} 个结果（含关系扩展）")
        return all_results

    def _expand_file_entities(self, file_path: str, exclude: Set[Tuple[str, str]] = None) -> List[Dict[str, Any]]:
        """沿 CONTAINS 关系扩展：查找同文件中的所有实体（全类型）"""
        exclude = exclude or set()
        results = []

        try:
            query = """
            MATCH (file:File {path: $file_path})-[:CONTAINS]->(entity)
            RETURN entity.name as name, labels(entity) as labels,
                   entity.signature as signature, entity.file_path as file_path,
                   entity.line_start as line_start, entity.line_end as line_end,
                   entity.parameters_text as parameters_text,
                   entity.return_type as return_type, entity.type as type
            """
            rows = self.graph_store.graph.run(query, file_path=file_path).data()

            for row in rows:
                name = row.get("name", "")
                if (file_path, name) in exclude:
                    continue

                labels = row.get("labels", [])
                entity_type = row.get("type", "")
                if not entity_type:
                    for label in labels:
                        if label in ("Function", "Class", "Struct", "Namespace", "Enum"):
                            entity_type = label.lower()
                            break

                if name:
                    results.append({
                        "file_path": file_path,
                        "entity_type": entity_type,
                        "entity_name": name,
                        "signature": row.get("signature", ""),
                        "line_start": row.get("line_start"),
                        "line_end": row.get("line_end"),
                        "parameters_text": row.get("parameters_text", ""),
                        "return_type": row.get("return_type", ""),
                        "search_type": "relation_expand",
                    })

        except Exception as e:
            logger.debug(f"关系扩展查询失败: {e}")

        return results

    # ==================== 查询意图分析（中英文增强） ====================

    def _analyze_query_intent(self, question: str) -> Dict[str, Any]:
        """分析查询意图 — 支持中英文模式提取 + 同义词扩展"""
        question_lower = question.lower()

        # 中文结构指示词
        structural_indicators = [
            "函数", "类", "方法", "调用", "继承", "包含", "定义", "实现",
            "接口", "模块", "服务", "组件", "变量", "属性", "配置",
        ]
        structural_keywords = [w for w in structural_indicators if w in question_lower]

        # 英文结构指示词
        en_structural = [
            "function", "class", "method", "call", "inherit", "contain",
            "define", "implement", "interface", "module", "service", "component",
            "variable", "property", "config", "struct", "enum", "namespace",
            "constructor", "destructor", "override", "virtual",
        ]
        for w in en_structural:
            if w in question_lower and w not in structural_keywords:
                structural_keywords.append(w)

        # ---- 提取实体 ----
        entities = []

        # 中文模式：如 "ExportCAD函数", "GcmpModel类"
        zh_entity_patterns = [
            r"(\w+)函数", r"(\w+)类", r"(\w+)方法",
            r"(\w+)的实现", r"(\w+)接口", r"(\w+)模块",
            r"(\w+)服务", r"(\w+)组件", r"(\w+)结构体",
        ]
        for pattern in zh_entity_patterns:
            matches = re.findall(pattern, question)
            entities.extend(matches)

        # 英文代码标识符（驼峰/下划线命名）
        code_id_matches = re.findall(r"\b([a-zA-Z][a-zA-Z0-9_]{2,})\b", question)
        code_stop_words = {
            "the", "this", "that", "what", "which", "who", "how", "why", "when", "where",
            "and", "not", "but", "for", "are", "was", "were", "has", "had", "does",
            "can", "will", "with", "from", "also", "just", "than", "then", "into",
            "about", "would", "could", "should", "there", "their", "these", "those",
            "being", "have", "been", "will", "shall", "may", "might", "must",
        }
        code_entities = [
            w for w in code_id_matches
            if w.lower() not in code_stop_words
            and (any(c.isupper() for c in w) or "_" in w)
        ]
        entities.extend(code_entities)

        # 英文模式："the XXX function/class/struct"
        en_entity_patterns = [
            r"\b([A-Za-z_]\w*)\s+(?:function|method|class|struct|enum|namespace|interface)\b",
            r"\b(?:function|method|class|struct)\s+(?:of|for|named?)\s+([A-Za-z_]\w*)\b",
        ]
        for pattern in en_entity_patterns:
            matches = re.findall(pattern, question, re.IGNORECASE)
            entities.extend([m for m in matches if m.lower() not in code_stop_words])

        # 去重
        entities = list(dict.fromkeys(entities))

        # 提取关键词 + 同义词扩展
        keywords = self._extract_keywords(question)
        expanded_keywords = self._expand_synonyms(keywords)

        strategy = "structural_search" if (structural_keywords or entities) else "semantic_search"

        return {
            "strategy": strategy,
            "structural_keywords": structural_keywords,
            "entities": entities,
            "keywords": keywords,
            "expanded_keywords": expanded_keywords,
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（中文 + 英文混合）"""
        zh_stop_words = {
            "什么", "怎么", "如何", "为什么", "哪里", "哪个", "哪些", "请问",
            "可以", "能够", "应该", "需要", "想要", "寻找", "查找", "搜索",
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
            "一个", "一种", "一下", "一些", "这个", "那个", "这些", "那些",
            "吗", "呢", "吧", "啊", "哦", "嗯",
        }
        words = re.findall(r"[\u4e00-\u9fff\w]+", text.lower())
        return [w for w in words if w not in zh_stop_words and len(w) > 1]

    @staticmethod
    def _expand_synonyms(keywords: List[str]) -> List[str]:
        """
        对关键词进行中英文同义词扩展

        例如: ["导出"] → ["导出", "export"]
        例如: ["function"] → ["function", "函数"]
        """
        expanded = []
        for kw in keywords:
            kw_lower = kw.lower()
            # 正向查找：中文 → 英文
            if kw in _ZH_EN_SYNONYMS:
                expanded.extend(_ZH_EN_SYNONYMS[kw])
            # 反向查找：英文 → 中文
            for zh, en_list in _ZH_EN_SYNONYMS.items():
                if kw_lower in [e.lower() for e in en_list]:
                    expanded.append(zh)
                    expanded.extend(en_list)
        return list(set(expanded))

    # ==================== 调试接口 ====================

    def debug_retrieval(self, question: str) -> Dict[str, Any]:
        """调试检索过程"""
        intent = self._analyze_query_intent(question)
        semantic_results = self._semantic_retrieval(question, intent)
        structural_results = self._structural_retrieval(question, intent)

        return {
            "question": question,
            "intent_analysis": intent,
            "semantic_results_count": len(semantic_results),
            "structural_results_count": len(structural_results),
            "semantic_results_preview": [
                {
                    "file_path": doc.metadata.get("file_path"),
                    "score": doc.metadata.get("_score"),
                    "content_preview": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content,
                }
                for doc in semantic_results[:5]
            ],
            "structural_results_preview": structural_results[:5],
        }
