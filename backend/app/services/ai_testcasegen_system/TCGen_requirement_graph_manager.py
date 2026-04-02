from py2neo import Graph, Node, Relationship, NodeMatcher
from typing import List, Dict, Any, Optional, Set
import time
from loguru import logger
from datetime import datetime
import json


class RequirementGraphManager:
    """需求图数据库管理器 - 扩展自基础的GraphDatabaseManager"""
    
    def __init__(self, uri: str, username: str, password: str):
        """
        初始化图数据库连接
        
        Args:
            uri: Neo4j数据库URI
            username: 用户名
            password: 密码
        """
        self.uri = uri
        self.username = username
        self.matcher = None  # 稍后初始化
        try:
            self.graph = Graph(uri, auth=(username, password))
            self.matcher = NodeMatcher(self.graph)
            self._test_connection()
        except Exception as e:
            raise ConnectionError(f"连接图数据库失败: {e}")
    
    def _test_connection(self):
        """测试数据库连接"""
        try:
            self.graph.run("RETURN 1")
            logger.info("✓ 图数据库连接成功")
        except Exception as e:
            raise ConnectionError(f"图数据库连接测试失败: {e}")
        self.initialized_constraints = set()
        
    # requirement_graph_manager.py - 修正版本

    def initialize_requirement_database(self):
        """初始化需求数据库的约束和索引 - 处理重复索引"""
        logger.info("初始化需求图数据库...")
        
        # =========== 1. 创建约束（确保唯一性） ===========
        constraints = [
            # 实体约束
            "CREATE CONSTRAINT requirement_id IF NOT EXISTS FOR (r:Requirement) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT user_story_id IF NOT EXISTS FOR (us:UserStory) REQUIRE us.id IS UNIQUE",
            "CREATE CONSTRAINT use_case_id IF NOT EXISTS FOR (uc:UseCase) REQUIRE uc.id IS UNIQUE",
            "CREATE CONSTRAINT business_goal_id IF NOT EXISTS FOR (bg:BusinessGoal) REQUIRE bg.id IS UNIQUE",
            "CREATE CONSTRAINT actor_id IF NOT EXISTS FOR (a:Actor) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT constraint_id IF NOT EXISTS FOR (c:Constraint) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT system_component_id IF NOT EXISTS FOR (sc:SystemComponent) REQUIRE sc.id IS UNIQUE",
            
            # 文档约束
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE"
        ]
        
        for constraint in constraints:
            try:
                self.graph.run(constraint)
                logger.debug(f"创建约束: {constraint}")
            except Exception as e:
                # 如果约束已存在，记录为info而不是warning
                if "already exists" in str(e).lower():
                    logger.debug(f"约束已存在: {constraint[:50]}...")
                else:
                    logger.warning(f"创建约束时警告: {e}")
        
        # =========== 2. 创建节点属性索引 ===========
        node_indexes = [
            # 通用索引
            "CREATE INDEX IF NOT EXISTS FOR (r:Requirement) ON (r.type)",
            "CREATE INDEX IF NOT EXISTS FOR (r:Requirement) ON (r.priority)",
            "CREATE INDEX IF NOT EXISTS FOR (r:Requirement) ON (r.status)",
            
            # 特定类型实体索引
            "CREATE INDEX IF NOT EXISTS FOR (us:UserStory) ON (us.priority)",
            "CREATE INDEX IF NOT EXISTS FOR (uc:UseCase) ON (uc.actor)",
            "CREATE INDEX IF NOT EXISTS FOR (a:Actor) ON (a.type)",
            
            # 文档相关索引
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.status)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.created_at)"
        ]
        
        for index in node_indexes:
            try:
                self.graph.run(index)
                logger.debug(f"创建节点索引: {index}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"节点索引已存在: {index[:50]}...")
                else:
                    logger.warning(f"创建节点索引时警告: {e}")
        
        # =========== 3. 创建全文索引 ===========
        fulltext_indexes = [
            "CREATE FULLTEXT INDEX requirement_search IF NOT EXISTS FOR (r:Requirement) ON EACH [r.name, r.description]",
            "CREATE FULLTEXT INDEX document_search IF NOT EXISTS FOR (d:Document) ON EACH [d.title, d.content]",
            "CREATE FULLTEXT INDEX user_story_search IF NOT EXISTS FOR (us:UserStory) ON EACH [us.name, us.description]",
            "CREATE FULLTEXT INDEX use_case_search IF NOT EXISTS FOR (uc:UseCase) ON EACH [uc.name, uc.description]"
        ]
        
        for index in fulltext_indexes:
            try:
                self.graph.run(index)
                logger.debug(f"创建全文索引: {index}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"全文索引已存在: {index[:50]}...")
                else:
                    logger.warning(f"创建全文索引时警告: {e}")
        
        # =========== 4. 创建关系属性索引 ===========
        # 注意：关系索引语法在Neo4j中可能不完全支持IF NOT EXISTS
        # 我们可以使用更通用的语法
        
        relationship_indexes = [
            # 针对DEPENDS_ON关系的confidence属性
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:DEPENDS_ON]-() ON (r.confidence)",
            
            # 针对IMPLEMENTS关系的status属性
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:IMPLEMENTS]-() ON (r.status)",
            
            # 针对CONFLICTS_WITH关系的severity属性
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:CONFLICTS_WITH]-() ON (r.severity)",
            
            # 针对TRACES_TO关系的verification_status属性
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:TRACES_TO]-() ON (r.verification_status)",
            
            # 针对CONTAINS关系的entity_type属性
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:CONTAINS]-() ON (r.entity_type)"
        ]
        
        for index in relationship_indexes:
            try:
                self.graph.run(index)
                logger.debug(f"创建关系索引: {index}")
            except Exception as e:
                # 根据Neo4j版本，关系索引可能不支持IF NOT EXISTS
                # 我们可以先检查索引是否存在
                if "already exists" in str(e).lower() or "EquivalentSchemaRuleAlreadyExists" in str(e):
                    logger.debug(f"关系索引已存在: {index[:50]}...")
                else:
                    # 尝试不使用IF NOT EXISTS的语法
                    try:
                        # 移除IF NOT EXISTS部分
                        simple_index = index.replace(" IF NOT EXISTS", "")
                        self.graph.run(simple_index)
                        logger.debug(f"使用简单语法创建关系索引: {simple_index}")
                    except Exception as e2:
                        if "already exists" in str(e2).lower() or "EquivalentSchemaRuleAlreadyExists" in str(e2):
                            logger.debug(f"关系索引已存在（简单语法）: {simple_index[:50]}...")
                        else:
                            logger.warning(f"创建关系索引失败: {index} - {e2}")
        
        logger.info("✓ 需求图数据库初始化完成")
    
    def create_requirement_document(self, doc_id: str, title: str, content: str, 
                                  metadata: Dict[str, Any] = None) -> Optional[Node]:
        """
        创建需求文档节点
        
        Args:
            doc_id: 文档ID
            title: 文档标题
            content: 文档内容
            metadata: 元数据
            
        Returns:
            创建的文档节点
        """
        try:
            doc_props = {
                "id": doc_id,
                "title": title,
                "content": content,
                "type": "Document",
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # 合并文档节点
            doc_node = self._merge_node("Document", "id", doc_props)
            
            if doc_node:
                logger.info(f"创建需求文档: {title} ({doc_id})")
            
            return doc_node
            
        except Exception as e:
            logger.error(f"创建需求文档失败: {e}")
            return None
    
    def _merge_node(self, label: str, primary_key: str, properties: Dict[str, Any]) -> Optional[Node]:
        """
        安全合并节点，防止冲突
        
        Args:
            label: 节点标签
            primary_key: 主键属性名
            properties: 节点属性字典
            
        Returns:
            合并后的节点，失败返回None
        """
        try:
            # 检查主键是否存在
            primary_value = properties.get(primary_key)
            if not primary_value:
                logger.warning(f"节点缺少主键 {primary_key}，跳过创建: {properties.get('name', 'unknown')}")
                return None
            
            processed_properties = self._convert_complex_types(properties)

            # 构建SET子句 - 更新所有属性
            set_clause = []
            params = {primary_key: primary_value}
            
            for key, value in processed_properties.items():
                if key != primary_key:
                    set_clause.append(f"n.{key} = ${key}")
                params[key] = value
            
            # 构建完整查询
            query = f"""
            MERGE (n:{label} {{{primary_key}: ${primary_key}}})
            """
            if set_clause:
                query += f" SET {', '.join(set_clause)}"
            query += " RETURN n"
            
            # 执行查询
            result = self.graph.run(query, **params).data()
            if result:
                return result[0]['n']
            return None
            
        except Exception as e:
            logger.error(f"合并节点失败 (label={label}, key={primary_key}): {e}")
            return None
        
    def _convert_complex_types(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        将复杂类型转换为Neo4j支持的格式
        
        Args:
            properties: 原始属性字典
            
        Returns:
            转换后的属性字典
        """
        converted = {}
        
        for key, value in properties.items():
            if value is None:
                # Neo4j不支持None，需要处理
                converted[key] = None
            elif isinstance(value, (dict, list)):
                # 字典和列表转换为JSON字符串
                try:
                    converted[key] = json.dumps(value, ensure_ascii=False)
                except Exception:
                    # 如果无法序列化，存储为字符串表示
                    converted[key] = str(value)
            elif isinstance(value, (int, float, str, bool)):
                # 基本类型直接存储
                converted[key] = value
            elif hasattr(value, '__dict__'):
                # 对象类型转换为字典再转JSON
                try:
                    converted[key] = json.dumps(value.__dict__, ensure_ascii=False)
                except Exception:
                    converted[key] = str(value)
            else:
                # 其他类型转换为字符串
                converted[key] = str(value)
        
        return converted

    def _merge_relationship(self, start_node: Node, rel_type: str, end_node: Node, 
                           properties: Dict[str, Any] = None) -> bool:
        """
        安全合并关系，防止重复创建
        
        Args:
            start_node: 起始节点
            rel_type: 关系类型
            end_node: 结束节点
            properties: 关系属性
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            # 构建MERGE查询
            query = f"""
            MATCH (a) WHERE id(a) = $start_id
            MATCH (b) WHERE id(b) = $end_id
            MERGE (a)-[r:{rel_type}]->(b)
            """
            
            params = {
                "start_id": start_node.identity,
                "end_id": end_node.identity
            }
            
            # 添加关系属性
            if properties:
                set_clause = []
                for key, value in properties.items():
                    set_clause.append(f"r.{key} = ${key}")
                    params[key] = value
                
                if set_clause:
                    query += f" SET {', '.join(set_clause)}"
            
            query += " RETURN r"
            
            self.graph.run(query, **params)
            return True
        except Exception as e:
            logger.error(f"合并关系失败: {e}")
            return False

    def build_requirement_graph(self, document_id: str, entities: List[Dict], 
                              relationships: List[Dict]) -> Dict[str, Any]:
        """
        构建需求知识图谱
        
        Args:
            document_id: 关联的文档ID
            entities: 实体列表
            relationships: 关系列表
            
        Returns:
            构建统计信息
        """
        logger.info(f"开始构建需求知识图谱 (文档: {document_id})...")
        
        # 获取文档节点
        doc_node = self.matcher.match("Document", id=document_id).first()
        if not doc_node:
            logger.error(f"文档不存在: {document_id}")
            return {}
        
        # 处理实体
        entity_nodes = {}
        for entity in entities:
            # 根据类型确定标签
            labels = self._get_entity_labels(entity["type"])
            entity["document_id"] = document_id
            
            # 创建实体节点
            entity_node = self._merge_node_with_labels(labels, "id", entity)
            
            if entity_node:
                entity_nodes[entity["id"]] = entity_node
                
                # 创建文档与实体的关系
                self._merge_relationship(
                    doc_node,
                    "CONTAINS",
                    entity_node,
                    {
                        "entity_type": entity["type"],
                        "created_at": time.time(),
                        "confidence": entity.get("confidence", 1.0)
                    }
                )
        
        logger.info(f"✓ 处理 {len(entity_nodes)} 个实体节点")
        
        # 处理关系
        relationship_count = 0
        for rel in relationships:
            source_id = rel["source_id"]
            target_id = rel["target_id"]
            
            if source_id in entity_nodes and target_id in entity_nodes:
                # 创建关系
                success = self._merge_relationship(
                    entity_nodes[source_id],
                    rel["type"],
                    entity_nodes[target_id],
                    {
                        "description": rel.get("description", ""),
                        "confidence": rel.get("confidence", 1.0),
                        "source": "document_parser",
                        "created_at": time.time()
                    }
                )
                
                if success:
                    relationship_count += 1
        
        logger.info(f"✓ 创建 {relationship_count} 个关系")
        
        # 构建统计信息
        stats = self.get_requirement_statistics(document_id)
        logger.info(f"✓ 需求知识图谱构建完成")
        
        return stats
    
    def _get_entity_labels(self, entity_type: str) -> List[str]:
        """根据实体类型获取节点标签"""
        # 基础标签映射
        type_label_map = {
            "FunctionalRequirement": ["Requirement", "Functional"],
            "NonFunctionalRequirement": ["Requirement", "NonFunctional"],
            "BusinessRule": ["BusinessRule"],
            "Constraint": ["Constraint"],
            "UserStory": ["UserStory"],
            "UseCase": ["UseCase"],
            "BusinessGoal": ["BusinessGoal"],
            "Actor": ["Actor"],
            "SystemComponent": ["SystemComponent"]
        }
        
        # 默认标签
        labels = type_label_map.get(entity_type, ["Requirement", "Entity"])
        labels.append("RequirementEntity")  # 通用标签
        
        return labels
    
    def _merge_node_with_labels(self, labels: List[str], primary_key: str, 
                              properties: Dict[str, Any]) -> Optional[Node]:
        """
        合并带有多标签的节点
        
        Args:
            labels: 节点标签列表
            primary_key: 主键属性名
            properties: 节点属性
            
        Returns:
            合并后的节点
        """
        try:
            # 构建标签字符串
            label_str = ":".join(labels)
            
            # 检查主键值
            primary_value = properties.get(primary_key)
            if not primary_value:
                logger.warning(f"节点缺少主键 {primary_key}")
                return None
            
            # 构建SET子句
            set_clause = []
            params = {primary_key: primary_value}
            
            for key, value in properties.items():
                if key != primary_key:
                    set_clause.append(f"n.{key} = ${key}")
                params[key] = value
            
            # 构建MERGE查询
            query = f"""
            MERGE (n:{label_str} {{{primary_key}: ${primary_key}}})
            """
            
            if set_clause:
                query += f" SET {', '.join(set_clause)}"
            
            query += " RETURN n"
            
            # 执行查询
            result = self.graph.run(query, **params).data()
            
            if result:
                return result[0]['n']
            
            return None
            
        except Exception as e:
            logger.error(f"合并带标签节点失败: {e}")
            return None
    
    def get_requirement_statistics(self, document_id: str = None) -> Dict[str, Any]:
        """获取需求图谱统计信息"""
        stats = {}
        
        if document_id:
            # 特定文档的统计
            queries = {
                "document_entities": f"""
                MATCH (d:Document {{id: '{document_id}'}})-[:CONTAINS]->(e)
                RETURN count(e) as count
                """,
                "document_relationships": f"""
                MATCH (d:Document {{id: '{document_id}'}})-[:CONTAINS]->(e1)
                MATCH (e1)-[r]->(e2)
                WHERE exists((d)-[:CONTAINS]->(e2))
                RETURN count(r) as count
                """,
                "entity_by_type": f"""
                MATCH (d:Document {{id: '{document_id}'}})-[:CONTAINS]->(e)
                RETURN labels(e) as labels, count(e) as count
                ORDER BY count DESC
                """,
                "relationship_by_type": f"""
                MATCH (d:Document {{id: '{document_id}'}})-[:CONTAINS]->(e1)
                MATCH (e1)-[r]->(e2)
                WHERE exists((d)-[:CONTAINS]->(e2))
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
                """
            }
        else:
            # 全局统计
            queries = {
                "total_documents": "MATCH (d:Document) RETURN count(d) as count",
                "total_entities": "MATCH (e:RequirementEntity) RETURN count(e) as count",
                "total_relationships": "MATCH ()-[r]->() RETURN count(r) as count",
                "top_documents": """
                MATCH (d:Document)-[:CONTAINS]->(e)
                RETURN d.title as title, d.id as id, count(e) as entity_count
                ORDER BY entity_count DESC
                LIMIT 10
                """
            }
        
        for key, query in queries.items():
            try:
                result = self.graph.run(query).data()
                if result:
                    stats[key] = result[0].get('count') if 'count' in result[0] else result
            except Exception as e:
                logger.error(f"获取统计 {key} 失败: {e}")
                stats[key] = None
        
        return stats
    
    def find_related_requirements(self, requirement_id: str, max_depth: int = 3) -> Dict[str, Any]:
        """
        查找相关需求
        
        Args:
            requirement_id: 需求ID
            max_depth: 最大遍历深度
            
        Returns:
            相关需求信息
        """
        try:
            # 使用APOC路径展开
            query = """
            MATCH (start {id: $req_id})
            CALL apoc.path.subgraphAll(start, {
                relationshipFilter: "DEPENDS_ON|IMPLEMENTS|CONFLICTS_WITH|TRACES_TO>",
                maxLevel: $max_depth
            }) YIELD nodes, relationships
            RETURN 
                [node in nodes | {
                    id: node.id,
                    name: node.name,
                    type: node.type,
                    labels: labels(node)
                }] as nodes,
                [rel in relationships | {
                    source_id: startNode(rel).id,
                    target_id: endNode(rel).id,
                    type: type(rel),
                    description: rel.description
                }] as relationships
            """
            
            result = self.graph.run(query, req_id=requirement_id, max_depth=max_depth).data()
            
            if result:
                return result[0]
            
            return {"nodes": [], "relationships": []}
            
        except Exception as e:
            logger.error(f"查找相关需求失败: {e}")
            return {"nodes": [], "relationships": []}
    
    def trace_requirement(self, requirement_id: str, direction: str = "both") -> Dict[str, Any]:
        """
        需求溯源
        
        Args:
            requirement_id: 需求ID
            direction: 方向（upstream/downstream/both）
            
        Returns:
            溯源路径
        """
        try:
            if direction == "upstream":
                # 追溯上游（依赖的来源）
                query = """
                MATCH (target {id: $req_id})
                MATCH path = (source)-[:TRACES_TO|DEPENDS_ON*]->(target)
                RETURN 
                    [node in nodes(path) | {
                        id: node.id,
                        name: node.name,
                        type: node.type
                    }] as trace_path,
                    length(path) as depth
                ORDER BY depth DESC
                LIMIT 10
                """
            elif direction == "downstream":
                # 追溯下游（依赖的目标）
                query = """
                MATCH (source {id: $req_id})
                MATCH path = (source)-[:IMPLEMENTS|TRACES_TO*]->(target)
                RETURN 
                    [node in nodes(path) | {
                        id: node.id,
                        name: node.name,
                        type: node.type
                    }] as trace_path,
                    length(path) as depth
                ORDER BY depth DESC
                LIMIT 10
                """
            else:
                # 双向追溯
                query = """
                MATCH (center {id: $req_id})
                CALL apoc.path.expandConfig(center, {
                    relationshipFilter: "DEPENDS_ON|IMPLEMENTS|TRACES_TO",
                    minLevel: 1,
                    maxLevel: 3,
                    bfs: true,
                    uniqueness: "NODE_GLOBAL"
                }) YIELD path
                RETURN 
                    [node in nodes(path) | {
                        id: node.id,
                        name: node.name,
                        type: node.type
                    }] as trace_path,
                    length(path) as depth
                ORDER BY depth
                LIMIT 20
                """
            
            result = self.graph.run(query, req_id=requirement_id).data()
            return {"traces": result}
            
        except Exception as e:
            logger.error(f"需求溯源失败: {e}")
            return {"traces": []}
    
    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """检测需求冲突"""
        try:
            query = """
            MATCH (r1)-[c:CONFLICTS_WITH]-(r2)
            RETURN 
                r1.id as req1_id,
                r1.name as req1_name,
                r2.id as req2_id,
                r2.name as req2_name,
                c.description as conflict_description,
                c.confidence as confidence
            ORDER BY c.confidence DESC
            """
            
            results = self.graph.run(query).data()
            return results
            
        except Exception as e:
            logger.error(f"检测冲突失败: {e}")
            return []
    
    def search_requirements(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索需求"""
        try:
            # 使用全文搜索
            query = """
            CALL db.index.fulltext.queryNodes("requirement_search", $keyword)
            YIELD node, score
            RETURN 
                node.id as id,
                node.name as name,
                node.description as description,
                node.type as type,
                labels(node) as labels,
                score
            ORDER BY score DESC
            LIMIT $limit
            """
            
            results = self.graph.run(query, keyword=keyword, limit=limit).data()
            return results
            
        except Exception as e:
            logger.error(f"搜索需求失败: {e}")
            return []
    
    def get_requirement_impact_analysis(self, requirement_id: str) -> Dict[str, Any]:
        """需求影响分析"""
        try:
            # 直接依赖
            query = """
            MATCH (r {id: $req_id})
            OPTIONAL MATCH (r)-[d:DEPENDS_ON]->(depends_on)
            OPTIONAL MATCH (r)<-[:DEPENDS_ON]-(depended_by)
            OPTIONAL MATCH (r)-[i:IMPLEMENTS]->(implements)
            OPTIONAL MATCH (r)<-[:IMPLEMENTS]-(implemented_by)
            OPTIONAL MATCH (r)-[c:CONFLICTS_WITH]-(conflicts_with)
            
            RETURN 
                r.id as requirement_id,
                r.name as requirement_name,
                r.type as requirement_type,
                COLLECT(DISTINCT {
                    relation: 'DEPENDS_ON',
                    direction: 'outgoing',
                    target_id: depends_on.id,
                    target_name: depends_on.name
                }) as outgoing_dependencies,
                COLLECT(DISTINCT {
                    relation: 'DEPENDS_ON',
                    direction: 'incoming',
                    source_id: depended_by.id,
                    source_name: depended_by.name
                }) as incoming_dependencies,
                COLLECT(DISTINCT {
                    relation: 'IMPLEMENTS',
                    direction: 'outgoing',
                    target_id: implements.id,
                    target_name: implements.name
                }) as outgoing_implementations,
                COLLECT(DISTINCT {
                    relation: 'IMPLEMENTS',
                    direction: 'incoming',
                    source_id: implemented_by.id,
                    source_name: implemented_by.name
                }) as incoming_implementations,
                COLLECT(DISTINCT {
                    relation: 'CONFLICTS_WITH',
                    target_id: conflicts_with.id,
                    target_name: conflicts_with.name
                }) as conflicts
            """
            
            result = self.graph.run(query, req_id=requirement_id).data()
            
            if result:
                return result[0]
            
            return {}
            
        except Exception as e:
            logger.error(f"需求影响分析失败: {e}")
            return {}
        
    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.graph.run("RETURN 1")
            return True
        except Exception:
            return False