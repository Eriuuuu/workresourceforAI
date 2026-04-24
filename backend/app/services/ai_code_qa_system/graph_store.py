from py2neo import Graph, Node, NodeMatcher
from typing import List, Dict, Any, Optional, Set
import re
import time
from loguru import logger


class GraphDatabaseManager:
    """图数据库管理器 - 使用复合主键区分同名实体"""

    # 支持的实体标签
    ENTITY_LABELS = {
        'file': 'File',
        'function': 'Function',
        'class': 'Class',
        'struct': 'Struct',
        'namespace': 'Namespace',
        'enum': 'Enum',
        'constructor': 'Function',
        'destructor': 'Function',
    }

    def __init__(self, uri: str, username: str, password: str):
        self.uri = uri
        self.username = username
        self.matcher = None
        try:
            self.graph = Graph(uri, auth=(username, password))
            self.matcher = NodeMatcher(self.graph)
            self._test_connection()
        except Exception as e:
            raise ConnectionError(f"连接图数据库失败: {e}")

    def _test_connection(self):
        try:
            self.graph.run("RETURN 1")
            logger.info("✓ 图数据库连接成功")
        except Exception as e:
            raise ConnectionError(f"图数据库连接测试失败: {e}")

    def initialize_database(self):
        """初始化数据库约束和索引 — 使用复合主键 qualified_name"""
        logger.info("初始化图数据库...")

        # ---- 清除旧版本遗留的 name 唯一约束 ----
        old_constraints = [
            "DROP CONSTRAINT function_name IF EXISTS",
            "DROP CONSTRAINT class_name IF EXISTS",
            "DROP CONSTRAINT struct_name IF EXISTS",
            "DROP CONSTRAINT namespace_name IF EXISTS",
            "DROP CONSTRAINT enum_name IF EXISTS",
            "DROP CONSTRAINT constructor_name IF EXISTS",
            "DROP CONSTRAINT destructor_name IF EXISTS",
        ]
        for c in old_constraints:
            try:
                self.graph.run(c)
                logger.info(f"  已清除旧约束: {c}")
            except Exception:
                pass  # 约束不存在时忽略

        # ---- 创建当前版本的约束 ----
        constraints = [
            "CREATE CONSTRAINT file_path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:CodeEntity) REQUIRE (e.qualified_name) IS UNIQUE",
        ]

        for constraint in constraints:
            try:
                self.graph.run(constraint)
            except Exception as e:
                logger.warning(f"创建约束时警告: {e}")

        # 索引：按 file_path、name 快速查找
        indexes = [
            "CREATE INDEX entity_file IF NOT EXISTS FOR (n:Function) ON (n.file_path)",
            "CREATE INDEX entity_file_class IF NOT EXISTS FOR (n:Class) ON (n.file_path)",
            "CREATE INDEX entity_file_struct IF NOT EXISTS FOR (n:Struct) ON (n.file_path)",
            "CREATE INDEX entity_file_ns IF NOT EXISTS FOR (n:Namespace) ON (n.file_path)",
            "CREATE INDEX entity_file_enum IF NOT EXISTS FOR (n:Enum) ON (n.file_path)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Function) ON (n.name)",
            "CREATE INDEX entity_name_class IF NOT EXISTS FOR (n:Class) ON (n.name)",
            "CREATE INDEX entity_name_struct IF NOT EXISTS FOR (n:Struct) ON (n.name)",
            "CREATE INDEX entity_name_ns IF NOT EXISTS FOR (n:Namespace) ON (n.name)",
            "CREATE INDEX file_name IF NOT EXISTS FOR (f:File) ON (f.name)",
        ]

        for index in indexes:
            try:
                self.graph.run(index)
            except Exception as e:
                logger.warning(f"创建索引时警告: {e}")

        logger.info("✓ 图数据库初始化完成")

    @staticmethod
    def _qualified_name(name: str, file_path: str, namespace: str = "", parent: str = "") -> str:
        """
        生成复合主键：namespace::parent::name@file_path
        确保同名实体在不同文件/命名空间/类中唯一
        """
        parts = []
        if namespace:
            parts.append(namespace)
        if parent:
            parts.append(parent)
        parts.append(name)
        return f"{'::'.join(parts)}@{file_path}"

    def _merge_entity_node(self, label: str, name: str, file_path: str,
                           properties: Dict[str, Any]) -> Optional[Node]:
        """
        使用复合主键 (qualified_name) 合并实体节点，支持同名实体在不同文件中共存
        """
        try:
            qn = self._qualified_name(
                name, file_path,
                properties.get('namespace', ''),
                properties.get('parent', '')
            )
            properties['qualified_name'] = qn

            set_clause = []
            params = {"qn": qn}
            for key, value in properties.items():
                if key != 'qualified_name':
                    set_clause.append(f"n.{key} = ${key}")
                    # 截断过长属性值，避免 Neo4j 属性值过大
                    if isinstance(value, str) and len(value) > 4000:
                        params[key] = value[:4000]
                    else:
                        params[key] = value

            query = f"MERGE (n:{label} {{qualified_name: $qn}})"
            if set_clause:
                query += f" SET {', '.join(set_clause)}"
            query += " RETURN n"

            result = self.graph.run(query, **params).data()
            if result:
                return result[0]['n']
            return None
        except Exception as e:
            logger.error(f"合并实体节点失败 (label={label}, name={name}): {e}")
            return None

    def _merge_file_node(self, file_path: str, file_name: str) -> Optional[Node]:
        """合并文件节点（File 的主键是 path，天然唯一）"""
        try:
            query = """
            MERGE (f:File {path: $path})
            SET f.name = $name, f.type = 'file'
            RETURN f
            """
            result = self.graph.run(query, path=file_path, name=file_name).data()
            return result[0]['f'] if result else None
        except Exception as e:
            logger.error(f"合并文件节点失败: {e}")
            return None

    def _merge_relationship(self, start_node: Node, rel_type: str, end_node: Node,
                           properties: Dict[str, Any] = None) -> bool:
        try:
            query = f"""
            MATCH (a) WHERE id(a) = $start_id
            MATCH (b) WHERE id(b) = $end_id
            MERGE (a)-[r:{rel_type}]->(b)
            """
            params = {"start_id": start_node.identity, "end_id": end_node.identity}

            if properties:
                set_clause = []
                for key, value in properties.items():
                    if isinstance(value, str) and len(value) > 4000:
                        value = value[:4000]
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

    # ==================== 图构建 ====================

    def build_code_graph(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建代码关系图 — 支持全部实体类型，使用复合主键区分同名实体

        Args:
            entities: code_parser 解析出的全部实体列表
        """
        logger.info("开始构建/更新代码关系图...")

        # ---- 0. 清除旧版本节点（缺少 qualified_name 属性的脏数据） ----
        entity_labels = ['Function', 'Class', 'Struct', 'Namespace', 'Enum', 'Constructor', 'Destructor']
        for lbl in entity_labels:
            try:
                self.graph.run(f"MATCH (n:{lbl}) WHERE n.qualified_name IS NULL DETACH DELETE n")
            except Exception as e:
                logger.warning(f"清除旧版 {lbl} 节点时警告: {e}")
        logger.info("  旧版节点清除完成")

        file_nodes: Dict[str, Node] = {}

        # ---- 1. 文件节点 ----
        files = [e for e in entities if e['type'] == 'file']
        for f in files:
            node = self._merge_file_node(f['file_path'], f['name'])
            if node:
                file_nodes[f['file_path']] = node
        logger.info(f"✓ 已处理 {len(file_nodes)} 个文件节点")

        # ---- 2. 所有代码实体节点（Function/Class/Struct/Namespace/Enum/Constructor/Destructor） ----
        entity_counts: Dict[str, int] = {}
        for entity in entities:
            etype = entity.get('type', '')
            if etype == 'file':
                continue

            label = self.ENTITY_LABELS.get(etype)
            if label is None:
                logger.debug(f"跳过未知实体类型: {etype}")
                continue

            # 构建节点属性
            props = {
                'name': entity.get('name', ''),
                'signature': (entity.get('signature', '') or '')[:4000],
                'file_path': entity.get('file_path', ''),
                'line_start': entity.get('line_start'),
                'line_end': entity.get('line_end'),
                'type': etype,
                'namespace': entity.get('namespace', ''),
                'parent': entity.get('parent', ''),
                'return_type': entity.get('return_type', ''),
                'is_template': entity.get('is_template', False),
                'is_virtual': entity.get('is_virtual', False),
                'is_static': entity.get('is_static', False),
            }

            # 序列化 parameters 为字符串存储
            params = entity.get('parameters', [])
            if params and isinstance(params, list):
                param_strs = [f"{p.get('type', '')} {p.get('name', '')}" for p in params if p.get('name') or p.get('type')]
                props['parameters_text'] = ', '.join(param_strs)[:2000]

            node = self._merge_entity_node(label, entity['name'], entity.get('file_path', ''), props)
            if node:
                entity_counts[etype] = entity_counts.get(etype, 0) + 1

                # 建立 File -[CONTAINS]-> Entity 关系
                fp = entity.get('file_path')
                if fp and fp in file_nodes:
                    self._merge_relationship(
                        file_nodes[fp], "CONTAINS", node,
                        {"entity_type": etype}
                    )

        logger.info(f"✓ 已处理实体: {entity_counts}")

        # ---- 3. 父子关系（Class CONTAINS Method, Namespace CONTAINS Class 等） ----
        self._build_parent_child_relationships(entities, file_nodes)

        # ---- 4. 调用关系（基于函数签名中的名称引用推断） ----
        self._infer_call_relationships_v2(entities)

        stats = self.get_graph_statistics()
        logger.info(f"✓ 代码关系图构建/更新完成")
        return stats

    def _build_parent_child_relationships(self, entities: List[Dict[str, Any]], _file_nodes: Dict[str, Node] = None):
        """
        构建父子包含关系：
        - Class -[CONTAINS]-> Function (成员函数)
        - Namespace -[CONTAINS]-> Class
        - Class -[CONTAINS]-> Struct (内部类)
        """
        _ = _file_nodes  # 保留参数签名兼容性，内部通过 Cypher 直接查询
        logger.info("构建父子包含关系...")

        # 构建 (qualified_name -> Node) 映射
        qname_to_node: Dict[str, Node] = {}
        for entity in entities:
            etype = entity.get('type', '')
            if etype == 'file':
                continue
            label = self.ENTITY_LABELS.get(etype)
            if label is None:
                continue
            qn = self._qualified_name(
                entity.get('name', ''), entity.get('file_path', ''),
                entity.get('namespace', ''), entity.get('parent', '')
            )
            # 通过 Cypher 查找已创建的节点
            try:
                result = self.graph.run(
                    f"MATCH (n:{label} {{qualified_name: $qn}}) RETURN n", qn=qn
                ).data()
                if result:
                    qname_to_node[qn] = result[0]['n']
            except Exception:
                pass

        # 建立 parent → child 关系
        created = 0
        for entity in entities:
            etype = entity.get('type', '')
            parent = entity.get('parent', '')
            fp = entity.get('file_path', '')
            ns = entity.get('namespace', '')

            if not parent and not ns:
                continue

            child_qn = self._qualified_name(entity.get('name', ''), fp, ns, parent)
            child_node = qname_to_node.get(child_qn)
            if not child_node:
                continue

            # 查找 parent 节点
            if parent:
                parent_qn = self._qualified_name(parent, fp, ns, '')
                parent_node = qname_to_node.get(parent_qn)
                if parent_node:
                    if self._merge_relationship(parent_node, "CONTAINS", child_node, {"relation": "member"}):
                        created += 1

            # 查找 namespace 节点
            if ns:
                ns_qn = self._qualified_name(ns, fp, '', '')
                ns_node = qname_to_node.get(ns_qn)
                if ns_node:
                    if self._merge_relationship(ns_node, "CONTAINS", child_node, {"relation": "namespace_member"}):
                        created += 1

        logger.info(f"✓ 创建了 {created} 个父子包含关系")

    def _infer_call_relationships_v2(self, entities: List[Dict[str, Any]]):
        """
        基于函数签名中的名称引用推断调用关系（V2：比 V1 更精确）

        策略：如果一个函数 A 的签名或参数类型中引用了函数 B 的名称，
        且 B 与 A 在同一个文件或 B 是全局可见的，则创建 A -[CALLS]-> B
        """
        logger.info("推断函数调用关系 (V2)...")

        # 收集所有函数/方法的 (name, file_path, qn)
        func_map: Dict[str, List[str]] = {}  # name -> [qualified_name, ...]
        for entity in entities:
            etype = entity.get('type', '')
            if etype in ('function', 'constructor', 'destructor'):
                name = entity.get('name', '')
                fp = entity.get('file_path', '')
                ns = entity.get('namespace', '')
                parent = entity.get('parent', '')
                qn = self._qualified_name(name, fp, ns, parent)
                func_map.setdefault(name, []).append(qn)

        # 收集所有函数签名中的引用名称
        call_pairs: Set[tuple] = set()
        for entity in entities:
            etype = entity.get('type', '')
            if etype not in ('function', 'constructor', 'destructor'):
                continue

            caller_name = entity.get('name', '')
            caller_fp = entity.get('file_path', '')
            caller_ns = entity.get('namespace', '')
            caller_parent = entity.get('parent', '')
            caller_qn = self._qualified_name(caller_name, caller_fp, caller_ns, caller_parent)
            signature = (entity.get('signature', '') or '').lower()

            # 在签名中查找其他函数名的引用
            for callee_name, callee_qns in func_map.items():
                if callee_name == caller_name:
                    continue
                # 简单检测：签名中是否出现被调用函数名（作为单词）
                # 使用正则确保是完整单词匹配
                pattern = re.compile(r'\b' + re.escape(callee_name) + r'\b')
                if pattern.search(signature):
                    # 优先同文件调用
                    for callee_qn in callee_qns:
                        if caller_fp in callee_qn:
                            call_pairs.add((caller_qn, callee_qn))
                            break
                    else:
                        # 跨文件调用
                        call_pairs.add((caller_qn, callee_qns[0]))

        # 创建 CALLS 关系
        created_count = 0
        for caller_qn, callee_qn in call_pairs:
            try:
                query = """
                MATCH (caller {qualified_name: $caller_qn})
                MATCH (callee {qualified_name: $callee_qn})
                MERGE (caller)-[r:CALLS]->(callee)
                SET r.inferred = true, r.confidence = 0.6
                RETURN r
                """
                self.graph.run(query, caller_qn=caller_qn, callee_qn=callee_qn)
                created_count += 1
            except Exception as e:
                logger.debug(f"创建调用关系失败: {caller_qn} -> {callee_qn}: {e}")

        logger.info(f"✓ 创建了 {created_count} 个调用关系")

    # ==================== 查询接口 ====================

    def query_related_entities(self, entity_name: str, entity_type: str = "Function") -> List[Dict[str, Any]]:
        """
        查询相关实体 — 支持同名多文件返回

        Args:
            entity_name: 实体名称（精确匹配）
            entity_type: 实体类型标签
        """
        label = self.ENTITY_LABELS.get(entity_type.lower(), entity_type)

        if label == "Function":
            query = """
            MATCH (entity:Function)
            WHERE entity.name = $name
            OPTIONAL MATCH (entity)-[:CALLS]->(called:Function)
            OPTIONAL MATCH (file:File)-[:CONTAINS]->(entity)
            RETURN entity.name as name, entity.signature as signature,
                   entity.file_path as file_path, entity.line_start as line_start,
                   entity.line_end as line_end, entity.parameters_text as parameters_text,
                   COLLECT(DISTINCT called.name) as calls,
                   file.path as file_path_src
            """
        elif label == "Class":
            query = """
            MATCH (entity:Class)
            WHERE entity.name = $name
            OPTIONAL MATCH (file:File)-[:CONTAINS]->(entity)
            RETURN entity.name as name, entity.signature as signature,
                   entity.file_path as file_path, entity.line_start as line_start,
                   entity.line_end as line_end,
                   file.path as file_path_src
            """
        else:
            query = """
            MATCH (entity)
            WHERE entity.name = $name
            OPTIONAL MATCH (file:File)-[:CONTAINS]->(entity)
            RETURN entity.name as name, entity.signature as signature,
                   entity.file_path as file_path, entity.line_start as line_start,
                   entity.line_end as line_end,
                   file.path as file_path_src
            """

        try:
            results = self.graph.run(query, name=entity_name).data()
            return results
        except Exception as e:
            logger.error(f"图查询失败: {e}")
            return []

    def search_entities_by_keyword(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        关键词模糊搜索 — 不区分大小写匹配名称和签名

        Args:
            keyword: 搜索关键词
            limit: 返回结果上限
        """
        query = """
        MATCH (entity)
        WHERE toLower(entity.name) CONTAINS toLower($keyword)
           OR toLower(entity.signature) CONTAINS toLower($keyword)
           OR toLower(COALESCE(entity.parameters_text, '')) CONTAINS toLower($keyword)
           OR toLower(COALESCE(entity.return_type, '')) CONTAINS toLower($keyword)
        RETURN entity.name as name, labels(entity) as labels,
               entity.signature as signature, entity.file_path as file_path,
               entity.type as type, entity.line_start as line_start,
               entity.line_end as line_end, entity.parameters_text as parameters_text,
               entity.return_type as return_type
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
        """查找包含指定实体的所有文件"""
        query = """
        MATCH (file:File)-[:CONTAINS]->(entity)
        WHERE entity.name = $name
        RETURN file.path as file_path, entity.type as entity_type,
               entity.signature as signature, entity.line_start as line_start
        """
        try:
            results = self.graph.run(query, name=entity_name).data()
            return results
        except Exception as e:
            logger.error(f"查找文件失败: {e}")
            return []

    def expand_entity_relations(self, entity_name: str, entity_type: str = "Function",
                                depth: int = 1) -> List[Dict[str, Any]]:
        """
        沿关系扩展：查找与指定实体相关的所有关联实体

        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            depth: 关系扩展深度（1=直接关系，2=二层关系）
        """
        label = self.ENTITY_LABELS.get(entity_type.lower(), entity_type)
        query = f"""
        MATCH (entity:{label})
        WHERE entity.name = $name
        // 沿 CALLS 扩展
        OPTIONAL MATCH (entity)-[:CALLS*1..{depth}]->(callee)
        // 沿 CONTAINS 反向扩展（文件包含的其他实体）
        OPTIONAL MATCH (file:File)-[:CONTAINS]->(entity)
        OPTIONAL MATCH (file)-[:CONTAINS]->(sibling)
        WHERE sibling <> entity
        // 沿 CONTAINS 正向扩展（类的成员）
        OPTIONAL MATCH (entity)-[:CONTAINS*1..{depth}]->(member)
        RETURN DISTINCT callee.name as callee_name, callee.type as callee_type,
               callee.file_path as callee_file, callee.signature as callee_sig,
               sibling.name as sibling_name, sibling.type as sibling_type,
               sibling.file_path as sibling_file, sibling.signature as sibling_sig,
               member.name as member_name, member.type as member_type,
               member.file_path as member_file, member.signature as member_sig
        LIMIT 100
        """
        try:
            results = self.graph.run(query, name=entity_name).data()
            related = []
            for r in results:
                for prefix in ['callee', 'sibling', 'member']:
                    name = r.get(f'{prefix}_name')
                    if name:
                        related.append({
                            'entity_name': name,
                            'entity_type': r.get(f'{prefix}_type', ''),
                            'file_path': r.get(f'{prefix}_file', ''),
                            'signature': r.get(f'{prefix}_sig', ''),
                            'relation': prefix,
                        })
            logger.debug(f"关系扩展: {entity_name} 找到 {len(related)} 个关联实体")
            return related
        except Exception as e:
            logger.error(f"关系扩展失败: {e}")
            return []

    # ==================== 通用接口 ====================

    def upsert_entity(self, entity: Dict[str, Any]) -> Optional[Node]:
        """插入或更新单个实体"""
        entity_type = entity.get('type', '')
        label = self.ENTITY_LABELS.get(entity_type)
        if label is None:
            logger.error(f"未知的实体类型: {entity_type}")
            return None

        if entity_type == 'file':
            return self._merge_file_node(entity.get('file_path', ''), entity.get('name', ''))

        node = self._merge_entity_node(label, entity.get('name', ''), entity.get('file_path', ''), entity)

        if 'file_path' in entity:
            file_node = self._merge_file_node(
                entity['file_path'],
                entity['file_path'].replace('\\', '/').split('/')[-1]
            )
            if file_node and node:
                self._merge_relationship(file_node, "CONTAINS", node, {"entity_type": entity_type})

        return node

    def delete_entity(self, label: str, primary_key: str, value: Any) -> bool:
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
        stats = {}
        grouped: Dict[str, list] = {}
        for entity in entities:
            etype = entity.get('type', 'unknown')
            grouped.setdefault(etype, []).append(entity)

        for etype, items in grouped.items():
            count = 0
            for entity in items:
                if self.upsert_entity(entity):
                    count += 1
            stats[etype] = count
            logger.info(f"批量处理 {etype}: 成功 {count}/{len(items)}")
        return stats

    def safe_build_graph(self, entities: List[Dict[str, Any]], max_retries: int = 3) -> Dict[str, Any]:
        for attempt in range(max_retries):
            try:
                logger.info(f"开始构建图数据库 (尝试 {attempt+1}/{max_retries})")
                return self.build_code_graph(entities)
            except Exception as e:
                logger.error(f"构建失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                logger.info(f"等待 {2 ** attempt} 秒后重试...")
                time.sleep(2 ** attempt)
        return {}

    def get_graph_statistics(self) -> Dict[str, Any]:
        queries = {
            "node_count": "MATCH (n) RETURN count(n) as count",
            "relationship_count": "MATCH ()-[r]->() RETURN count(r) as count",
            "file_count": "MATCH (f:File) RETURN count(f) as count",
            "function_count": "MATCH (f:Function) RETURN count(f) as count",
            "class_count": "MATCH (c:Class) RETURN count(c) as count",
            "struct_count": "MATCH (s:Struct) RETURN count(s) as count",
            "namespace_count": "MATCH (ns:Namespace) RETURN count(ns) as count",
            "enum_count": "MATCH (e:Enum) RETURN count(e) as count",
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
        try:
            self.graph.run("RETURN 1")
            return True
        except Exception:
            return False

    def clear_database(self) -> bool:
        try:
            self.graph.run("MATCH (n) DETACH DELETE n")
            logger.warning("数据库已清空")
            return True
        except Exception as e:
            logger.error(f"清空数据库失败: {e}")
            return False