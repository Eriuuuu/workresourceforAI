from py2neo import Graph, Node, Relationship, NodeMatcher
from typing import List, Dict, Any, Optional
import re
import time
from loguru import logger


class GraphDatabaseManager:
    """图数据库管理器 - 使用MERGE操作避免冲突"""
    
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
    
    def initialize_database(self):
        """初始化数据库约束和索引"""
        logger.info("初始化图数据库...")
        
        constraints = [
            "CREATE CONSTRAINT file_path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT function_name IF NOT EXISTS FOR (func:Function) REQUIRE func.name IS UNIQUE",
            "CREATE CONSTRAINT class_name IF NOT EXISTS FOR (cls:Class) REQUIRE cls.name IS UNIQUE",
            "CREATE CONSTRAINT struct_name IF NOT EXISTS FOR (s:Struct) REQUIRE s.name IS UNIQUE"
        ]
        
        for constraint in constraints:
            try:
                self.graph.run(constraint)
            except Exception as e:
                logger.warning(f"创建约束时警告: {e}")
        
        # 创建索引以提高查询性能
        indexes = [
            "CREATE INDEX function_file IF NOT EXISTS FOR (f:Function) ON (f.file_path)",
            "CREATE INDEX class_file IF NOT EXISTS FOR (c:Class) ON (c.file_path)",
            "CREATE INDEX struct_file IF NOT EXISTS FOR (s:Struct) ON (s.file_path)",
            "CREATE INDEX file_name IF NOT EXISTS FOR (f:File) ON (f.name)"
        ]
        
        for index in indexes:
            try:
                self.graph.run(index)
            except Exception as e:
                logger.warning(f"创建索引时警告: {e}")
        
        logger.info("✓ 图数据库初始化完成")
    
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
            
            # 构建SET子句 - 更新所有属性（包括主键，以确保一致性）
            set_clause = []
            params = {primary_key: primary_value}
            
            for key, value in properties.items():
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
    
    def build_code_graph(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建代码关系图 - 使用MERGE避免冲突
        
        Args:
            entities: 实体列表，每个实体是一个字典
            
        Returns:
            构建统计信息
        """
        logger.info("开始构建/更新代码关系图...")
        
        # 按类型分组实体
        files = [e for e in entities if e['type'] == 'file']
        functions = [e for e in entities if e['type'] == 'function']
        classes = [e for e in entities if e['type'] == 'class']
        structs = [e for e in entities if e['type'] == 'struct']
        
        logger.info(f"处理 {len(files)} 个文件, {len(functions)} 个函数, {len(classes)} 个类, {len(structs)} 个结构体")
        
        # 创建或更新文件节点
        file_nodes = {}
        for file_entity in files:
            file_props = {
                "path": file_entity['file_path'],
                "name": file_entity['name'],
                "type": "file"
            }
            file_node = self._merge_node("File", "path", file_props)
            if file_node:
                file_nodes[file_entity['file_path']] = file_node
                logger.debug(f"处理文件: {file_entity['file_path']}")
        
        logger.info(f"✓ 已处理 {len(file_nodes)} 个文件节点")
        
        # 创建或更新函数节点
        function_nodes = {}
        for func in functions:
            func_props = {
                "name": func['name'],
                "signature": func.get('signature', ''),
                "file_path": func.get('file_path', ''),
                "line_start": func.get('line_start'),
                "line_end": func.get('line_end'),
                "type": "function"
            }
            func_node = self._merge_node("Function", "name", func_props)
            if func_node:
                function_nodes[func['name']] = func_node
                
                # 关联函数和文件（使用MERGE避免重复关系）
                file_path = func.get('file_path')
                if file_path and file_path in file_nodes:
                    self._merge_relationship(
                        file_nodes[file_path], 
                        "CONTAINS", 
                        func_node,
                        {"entity_type": "function", "since": time.time()}
                    )
        
        logger.info(f"✓ 已处理 {len(function_nodes)} 个函数节点")
        
        # 创建或更新类节点
        class_nodes = {}
        for cls in classes:
            class_props = {
                "name": cls['name'],
                "signature": cls.get('signature', ''),
                "file_path": cls.get('file_path', ''),
                "line_start": cls.get('line_start'),
                "line_end": cls.get('line_end'),
                "type": "class"
            }
            class_node = self._merge_node("Class", "name", class_props)
            if class_node:
                class_nodes[cls['name']] = class_node
                
                # 关联类和文件
                file_path = cls.get('file_path')
                if file_path and file_path in file_nodes:
                    self._merge_relationship(
                        file_nodes[file_path], 
                        "CONTAINS", 
                        class_node,
                        {"entity_type": "class"}
                    )
        
        logger.info(f"✓ 已处理 {len(class_nodes)} 个类节点")
        
        # 创建或更新结构体节点
        struct_nodes = {}
        for struct in structs:
            struct_props = {
                "name": struct['name'],
                "signature": struct.get('signature', ''),
                "file_path": struct.get('file_path', ''),
                "line_start": struct.get('line_start'),
                "line_end": struct.get('line_end'),
                "type": "struct"
            }
            struct_node = self._merge_node("Struct", "name", struct_props)
            if struct_node:
                struct_nodes[struct['name']] = struct_node
                
                # 关联结构体和文件
                file_path = struct.get('file_path')
                if file_path and file_path in file_nodes:
                    self._merge_relationship(
                        file_nodes[file_path], 
                        "CONTAINS", 
                        struct_node,
                        {"entity_type": "struct"}
                    )
        
        logger.info(f"✓ 已处理 {len(struct_nodes)} 个结构体节点")
        
        # 推断调用关系（使用MERGE）
        self._infer_call_relationships(functions, function_nodes)
        
        stats = self.get_graph_statistics()
        logger.info(f"✓ 代码关系图构建/更新完成")
        return stats
    
    def _infer_call_relationships(self, functions: List[Dict[str, Any]], function_nodes: Dict[str, Node]):
        """
        推断函数调用关系 - 使用MERGE避免重复
        
        Args:
            functions: 函数实体列表
            function_nodes: 函数节点字典
        """
        call_relationships = []
        
        logger.info("推断函数调用关系...")
        
        # 示例：根据函数名和签名推断调用关系
        for func in functions:
            caller_name = func['name']
            if caller_name not in function_nodes:
                continue
            
            # 这里可以添加更复杂的调用关系推断逻辑
            # 例如，分析函数签名中的参数类型
            signature = func.get('signature', '').lower()
            
            # 示例1：如果函数名包含"process"或"handle"，可能调用其他处理函数
            if 'process' in caller_name.lower() or 'handle' in caller_name.lower():
                for other_func_name, other_func_node in function_nodes.items():
                    if (other_func_name != caller_name and 
                        ('execute' in other_func_name.lower() or 'run' in other_func_name.lower())):
                        call_relationships.append((caller_name, other_func_name))
            
            # 示例2：根据参数类型推断调用关系
            if 'error' in signature or 'exception' in signature:
                for other_func_name, other_func_node in function_nodes.items():
                    if (other_func_name != caller_name and 
                        ('log' in other_func_name.lower() or 'report' in other_func_name.lower())):
                        call_relationships.append((caller_name, other_func_name))
        
        # 创建调用关系（使用MERGE）
        created_count = 0
        for caller_name, callee_name in call_relationships:
            if caller_name in function_nodes and callee_name in function_nodes:
                success = self._merge_relationship(
                    function_nodes[caller_name], 
                    "CALLS", 
                    function_nodes[callee_name],
                    {"inferred": True, "confidence": 0.7}  # 标记为推断的关系
                )
                if success:
                    created_count += 1
        
        logger.info(f"创建/更新了 {created_count} 个调用关系")
    
    def upsert_entity(self, entity: Dict[str, Any]) -> Optional[Node]:
        """
        插入或更新单个实体，适用于增量更新场景
        
        Args:
            entity: 实体字典
            
        Returns:
            更新后的节点，失败返回None
        """
        label_map = {
            'file': ('File', 'path'),
            'function': ('Function', 'name'),
            'class': ('Class', 'name'),
            'struct': ('Struct', 'name')
        }
        
        entity_type = entity.get('type')
        if entity_type not in label_map:
            logger.error(f"未知的实体类型: {entity_type}")
            return None
        
        label, primary_key = label_map[entity_type]
        node = self._merge_node(label, primary_key, entity)
        
        # 如果实体有关联的文件，创建关系
        if 'file_path' in entity and entity_type != 'file':
            file_node = self._merge_node("File", "path", {
                "path": entity['file_path'],
                "name": entity['file_path'].split('/')[-1] if '/' in entity['file_path'] else entity['file_path'],
                "type": "file"
            })
            if file_node and node:
                self._merge_relationship(
                    file_node, 
                    "CONTAINS", 
                    node,
                    {"entity_type": entity_type, "updated_at": time.time()}
                )
        
        return node
    
    def delete_entity(self, label: str, primary_key: str, value: Any) -> bool:
        """
        删除指定实体及其关系
        
        Args:
            label: 节点标签
            primary_key: 主键属性名
            value: 主键值
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            query = f"""
            MATCH (n:{label} {{{primary_key}: $value}})
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """
            result = self.graph.run(query, value=value).data()
            deleted_count = result[0]['deleted_count'] if result else 0
            
            logger.info(f"删除 {label} ({primary_key}={value}): {deleted_count} 个节点")
            return deleted_count > 0
        except Exception as e:
            logger.error(f"删除实体失败: {e}")
            return False
    
    def batch_upsert_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        批量更新实体，提高性能
        
        Args:
            entities: 实体列表
            
        Returns:
            各类实体处理数量的统计
        """
        stats = {}
        
        # 按类型分组处理
        grouped = {}
        for entity in entities:
            etype = entity.get('type')
            if etype not in grouped:
                grouped[etype] = []
            grouped[etype].append(entity)
        
        # 批量处理每种类型
        for etype, items in grouped.items():
            count = 0
            for entity in items:
                node = self.upsert_entity(entity)
                if node:
                    count += 1
            
            stats[etype] = count
            logger.info(f"批量处理 {etype}: 成功 {count}/{len(items)}")
        
        return stats
    
    def safe_build_graph(self, entities: List[Dict[str, Any]], max_retries: int = 3) -> Dict[str, Any]:
        """
        带重试机制的图构建，提高鲁棒性
        
        Args:
            entities: 实体列表
            max_retries: 最大重试次数
            
        Returns:
            构建统计信息
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"开始构建图数据库 (尝试 {attempt+1}/{max_retries})")
                return self.build_code_graph(entities)
            except Exception as e:
                logger.error(f"构建失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error("达到最大重试次数，构建失败")
                    raise
                logger.info(f"等待 {2 ** attempt} 秒后重试...")
                time.sleep(2 ** attempt)  # 在线程池中运行，不阻塞事件循环
        
        return {}
    
    def query_related_entities(self, entity_name: str, entity_type: str = "Function") -> List[Dict[str, Any]]:
        """
        查询相关实体
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            
        Returns:
            相关实体信息列表
        """
        if entity_type == "Function":
            query = """
            MATCH (entity:Function {name: $name})
            OPTIONAL MATCH (entity)-[:CALLS]->(called:Function)
            OPTIONAL MATCH (entity)-[:CONTAINS]-(file:File)
            RETURN entity.name as name, entity.signature as signature,
                   COLLECT(DISTINCT called.name) as calls,
                   file.path as file_path
            """
        elif entity_type == "Class":
            query = """
            MATCH (entity:Class {name: $name})
            OPTIONAL MATCH (entity)-[:CONTAINS]-(file:File)
            RETURN entity.name as name, entity.signature as signature,
                   file.path as file_path
            """
        else:
            query = """
            MATCH (entity {name: $name})
            OPTIONAL MATCH (entity)-[:CONTAINS]-(file:File)
            RETURN entity.name as name, entity.signature as signature,
                   file.path as file_path
            """
        
        try:
            results = self.graph.run(query, name=entity_name).data()
            return results
        except Exception as e:
            logger.error(f"图查询失败: {e}")
            return []

    def search_entities_by_keyword(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        根据关键词模糊搜索图数据库中的实体（名称或签名包含关键词）
        
        Args:
            keyword: 搜索关键词（支持部分匹配）
            limit: 返回结果上限
            
        Returns:
            匹配的实体列表
        """
        query = """
        MATCH (entity)
        WHERE entity.name CONTAINS $keyword
           OR entity.signature CONTAINS $keyword
        RETURN entity.name as name, labels(entity) as labels,
               entity.signature as signature, entity.file_path as file_path,
               entity.type as type
        LIMIT $limit
        """
        try:
            results = self.graph.run(query, keyword=keyword, limit=limit).data()
            logger.debug(f"图模糊搜索 keyword='{keyword}' 找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"图模糊搜索失败: {e}")
            return []
    
    def find_files_containing_entity(self, entity_name: str) -> List[Dict[str, Any]]:
        """
        查找包含指定实体的文件
        
        Args:
            entity_name: 实体名称
            
        Returns:
            文件信息列表
        """
        query = """
        MATCH (entity {name: $name})-[:CONTAINS]-(file:File)
        RETURN file.path as file_path, entity.type as entity_type,
               entity.signature as signature
        """
        
        try:
            results = self.graph.run(query, name=entity_name).data()
            return results
        except Exception as e:
            logger.error(f"查找文件失败: {e}")
            return []
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """获取图数据库统计信息"""
        queries = {
            "node_count": "MATCH (n) RETURN count(n) as count",
            "relationship_count": "MATCH ()-[r]->() RETURN count(r) as count",
            "file_count": "MATCH (f:File) RETURN count(f) as count",
            "function_count": "MATCH (f:Function) RETURN count(f) as count",
            "class_count": "MATCH (c:Class) RETURN count(c) as count",
            "struct_count": "MATCH (s:Struct) RETURN count(s) as count",
            "call_relationship_count": "MATCH ()-[r:CALLS]->() RETURN count(r) as count",
            "contains_relationship_count": "MATCH ()-[r:CONTAINS]->() RETURN count(r) as count"
        }
        
        stats = {}
        for key, query in queries.items():
            try:
                result = self.graph.run(query).data()
                if result:
                    stats[key] = result[0]['count']
            except Exception as e:
                logger.error(f"获取统计 {key} 失败: {e}")
                stats[key] = 0
        
        return stats
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.graph.run("RETURN 1")
            return True
        except Exception:
            return False
    
    def clear_database(self) -> bool:
        """
        清空数据库（谨慎使用）
        
        Returns:
            成功返回True，失败返回False
        """
        try:
            self.graph.run("MATCH (n) DETACH DELETE n")
            logger.warning("数据库已清空")
            return True
        except Exception as e:
            logger.error(f"清空数据库失败: {e}")
            return False