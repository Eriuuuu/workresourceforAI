from typing import Dict, List, Any, Optional, Tuple
import json
import re
from dataclasses import dataclass
from enum import Enum
from loguru import logger

class RequirementType(Enum):
    """需求类型枚举"""
    FUNCTIONAL = "Functional"
    NON_FUNCTIONAL = "NonFunctional"
    BUSINESS_RULE = "BusinessRule"
    CONSTRAINT = "Constraint"
    USER_STORY = "UserStory"
    USE_CASE = "UseCase"
    BUSINESS_GOAL = "BusinessGoal"

class RelationshipType(Enum):
    """关系类型枚举"""
    DEPENDS_ON = "DEPENDS_ON"
    IMPLEMENTS = "IMPLEMENTS"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    CONTAINS = "CONTAINS"
    TRACES_TO = "TRACES_TO"
    VALIDATES = "VALIDATES"
    REFINES = "REFINES"
    DERIVED_FROM = "DERIVED_FROM"

@dataclass
class RequirementEntity:
    """需求实体基类"""
    id: str
    name: str
    description: str
    type: RequirementType
    priority: str = "Medium"
    status: str = "Draft"
    version: str = "1.0"
    source: str = ""
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "priority": self.priority,
            "status": self.status,
            "version": self.version,
            "source": self.source,
            "metadata": self.metadata or {}
        }

@dataclass
class RequirementRelationship:
    """需求关系"""
    source_id: str
    target_id: str
    type: RelationshipType
    description: str = ""
    confidence: float = 1.0
    properties: Dict[str, Any] = None

class RequirementParser:
    """需求文档解析器 - 使用大模型提取实体和关系"""
    
    def __init__(self, llm_system):
        """
        初始化解析器
        
        Args:
            llm_system: 大模型系统实例
        """
        self.llm = llm_system
        self.system_prompt = """你是一个专业的系统需求分析专家。请从需求文档中提取结构化的实体和关系信息。对需求文档的分析需全面，不可以只分析部分内容。输出内容需完整，不可省略。

你需要提取以下信息：

1. **实体类型**：
   - FunctionalRequirement: 功能性需求
   - NonFunctionalRequirement: 非功能性需求（性能、安全、可用性等）
   - BusinessRule: 业务规则
   - Constraint: 约束条件
   - UserStory: 用户故事
   - UseCase: 用例
   - BusinessGoal: 业务目标
   - Actor: 参与者
   - SystemComponent: 系统组件

2. **属性要求**：
   - 每个实体必须包含：id（唯一标识符）、name、description
   - 可选属性：priority（High/Medium/Low）、status、version、source

3. **关系类型**：
   - DEPENDS_ON: A依赖于B
   - IMPLEMENTS: A实现B
   - CONFLICTS_WITH: A与B冲突
   - CONTAINS: A包含B
   - TRACES_TO: A追溯到B
   - VALIDATES: A验证B
   - REFINES: A细化B
   - DERIVED_FROM: A派生于B

4. **输出格式**：
   请以严格的JSON格式返回：
   {
     "entities": [
       {
         "id": "REQ-00000007",
         "name": "用户登录",
         "description": "用户可以通过用户名密码登录系统",
         "type": "FunctionalRequirement",
         "priority": "High",
         "status": "Approved"
       }
     ],
     "relationships": [
       {
         "source_id": "REQ-00000007",
         "target_id": "REQ-00000006",
         "type": "DEPENDS_ON",
         "description": "登录功能依赖于用户管理模块"
       }
     ]
   }

注意：
1. 为每个实体生成唯一的8位数ID（可以使用前缀如REQ-、UC-、US-等）
2. 保持关系的准确性
3. 只提取文档中明确提到的需求，不要自行添加
4. 对于模糊的描述，可以添加confidence字段表示置信度
"""
    
    def parse_requirement_document(self, document: str, chunk_size: int = 3000) -> Tuple[List[Dict], List[Dict]]:
        """
        解析需求文档
        
        Args:
            document: 需求文档内容
            chunk_size: 分块大小
            
        Returns:
            (entities, relationships) 实体和关系列表
        """
        logger.info("开始解析需求文档...")
        
        # 如果文档过长，进行分块处理
        if len(document) > chunk_size:
            return self._parse_large_document(document, chunk_size)
        else:
            return self._parse_single_chunk(document)
    
    def _parse_single_chunk(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        """解析单个文本块"""
        try:
            # 构建消息
            messages =f"请从以下需求文档中提取实体和关系：\n\n{text}"
            
            # 调用大模型
            response = self.llm.ask_question(messages,self.system_prompt)
            
            # 解析JSON响应
            parsed_data = self._extract_json_from_response(response["answer"])
            
            # 验证和清洗数据
            entities = self._validate_and_clean_entities(parsed_data.get("entities", []))
            relationships = self._validate_and_clean_relationships(
                parsed_data.get("relationships", []),
                entities
            )
            
            logger.info(f"解析完成: 提取到 {len(entities)} 个实体, {len(relationships)} 个关系")
            return entities, relationships
            
        except Exception as e:
            logger.error(f"解析需求文档失败: {e}")
            return [], []
    
    def _parse_large_document(self, document: str, chunk_size: int) -> Tuple[List[Dict], List[Dict]]:
        """解析大型文档（分块处理）"""
        logger.info("文档较大，进行分块处理...")
        
        # 按段落分块（基于Markdown结构）
        chunks = self._split_document_by_sections(document)
        
        all_entities = []
        all_relationships = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"处理第 {i+1}/{len(chunks)} 个块...")
            entities, relationships = self._parse_single_chunk(chunk)
            
            # 为实体添加分块信息
            for entity in entities:
                entity["chunk_id"] = i
                entity["chunk_total"] = len(chunks)
            
            all_entities.extend(entities)
            all_relationships.extend(relationships)
        
        # 合并重复实体（基于ID）
        merged_entities = self._merge_entities(all_entities)
        
        # 合并关系并解决跨块关系
        merged_relationships = self._merge_relationships(all_relationships, merged_entities)
        
        # 最后对整个文档进行一次高层级的提取（识别跨块关系）
        global_entities, global_relationships = self._extract_global_context(
            document, merged_entities, merged_relationships
        )
        
        # 合并全局提取结果
        final_entities = self._merge_entities(merged_entities + global_entities)
        final_relationships = self._merge_relationships(
            merged_relationships + global_relationships, 
            final_entities
        )
        
        logger.info(f"分块解析完成: 总共 {len(final_entities)} 个实体, {len(final_relationships)} 个关系")
        return final_entities, final_relationships
    
    def _split_document_by_sections(self, document: str) -> List[str]:
        """按章节分割Markdown文档"""
        # 基于Markdown标题分割
        sections = []
        lines = document.split('\n')
        
        current_section = []
        for line in lines:
            # 检测标题（#,##,###）
            if re.match(r'^#{1,3}\s+', line):
                if current_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
            current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        # 如果章节太少，按段落分割
        if len(sections) < 3:
            paragraphs = document.split('\n\n')
            sections = ['\n\n'.join(paragraphs[i:i+5]) for i in range(0, len(paragraphs), 5)]
        
        return sections
    
    def _extract_json_from_response(self, response: str) -> Dict:
        """从大模型响应中提取JSON"""
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            json_pattern = r'```json\s*(.*?)\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if matches:
                try:
                    return json.loads(matches[0])
                except json.JSONDecodeError:
                    pass
            
            # 尝试提取花括号内的内容
            brace_pattern = r'\{.*\}'
            matches = re.findall(brace_pattern, response, re.DOTALL)
            
            if matches:
                try:
                    return json.loads(matches[0])
                except json.JSONDecodeError:
                    pass
            
            logger.error(f"无法从响应中提取JSON: {response[:200]}...")
            return {"entities": [], "relationships": []}
    
    def _validate_and_clean_entities(self, entities: List[Dict]) -> List[Dict]:
        """验证和清洗实体"""
        valid_entities = []
        seen_ids = set()
        
        for entity in entities:
            try:
                # 必需字段检查
                if not entity.get("id") or not entity.get("name"):
                    logger.warning(f"实体缺少必需字段: {entity}")
                    continue
                
                # ID去重
                if entity["id"] in seen_ids:
                    logger.warning(f"重复的实体ID: {entity['id']}")
                    continue
                
                seen_ids.add(entity["id"])
                
                # 标准化类型
                entity["type"] = self._normalize_entity_type(entity.get("type", "Requirement"))
                
                # 确保有描述
                if not entity.get("description"):
                    entity["description"] = entity.get("name", "")
                
                # 添加默认值
                entity.setdefault("priority", "Medium")
                entity.setdefault("status", "Draft")
                entity.setdefault("version", "1.0")
                entity.setdefault("source", "")
                
                valid_entities.append(entity)
                
            except Exception as e:
                logger.error(f"验证实体时出错: {e}, 实体: {entity}")
        
        return valid_entities
    
    def _validate_and_clean_relationships(self, relationships: List[Dict], 
                                        entities: List[Dict]) -> List[Dict]:
        """验证和清洗关系"""
        valid_relationships = []
        entity_ids = {e["id"] for e in entities}
        
        for rel in relationships:
            try:
                # 必需字段检查
                if not all(k in rel for k in ["source_id", "target_id", "type"]):
                    logger.warning(f"关系缺少必需字段: {rel}")
                    continue
                
                # 确保实体存在
                if rel["source_id"] not in entity_ids:
                    logger.warning(f"关系的源实体不存在: {rel['source_id']}")
                    continue
                
                if rel["target_id"] not in entity_ids:
                    logger.warning(f"关系的目标实体不存在: {rel['target_id']}")
                    continue
                
                # 标准化关系类型
                rel["type"] = self._normalize_relationship_type(rel["type"])
                
                # 添加默认值
                rel.setdefault("description", "")
                rel.setdefault("confidence", 1.0)
                
                valid_relationships.append(rel)
                
            except Exception as e:
                logger.error(f"验证关系时出错: {e}, 关系: {rel}")
        
        return valid_relationships
    
    def _normalize_entity_type(self, entity_type: str) -> str:
        """标准化实体类型"""
        type_map = {
            "功能性需求": "FunctionalRequirement",
            "功能性": "FunctionalRequirement",
            "功能需求": "FunctionalRequirement",
            "非功能性需求": "NonFunctionalRequirement",
            "非功能性": "NonFunctionalRequirement",
            "性能需求": "NonFunctionalRequirement",
            "业务规则": "BusinessRule",
            "约束": "Constraint",
            "约束条件": "Constraint",
            "用户故事": "UserStory",
            "用例": "UseCase",
            "业务目标": "BusinessGoal",
            "参与者": "Actor",
            "系统组件": "SystemComponent",
            "模块": "SystemComponent"
        }
        
        # 去除空格和特殊字符
        normalized = entity_type.strip().replace(" ", "")
        
        if normalized in type_map:
            return type_map[normalized]
        
        # 如果包含关键词，进行映射
        for key, value in type_map.items():
            if key in entity_type:
                return value
        
        # 默认为FunctionalRequirement
        return "FunctionalRequirement"
    
    def _normalize_relationship_type(self, rel_type: str) -> str:
        """标准化关系类型"""
        type_map = {
            "依赖": "DEPENDS_ON",
            "依赖于": "DEPENDS_ON",
            "依赖关系": "DEPENDS_ON",
            "实现": "IMPLEMENTS",
            "冲突": "CONFLICTS_WITH",
            "包含": "CONTAINS",
            "包含在": "CONTAINS",
            "追溯": "TRACES_TO",
            "验证": "VALIDATES",
            "细化": "REFINES",
            "派生": "DERIVED_FROM"
        }
        
        # 去除空格和特殊字符
        normalized = rel_type.strip().replace(" ", "").upper()
        
        if normalized in type_map.values():
            return normalized
        
        # 中文映射
        if rel_type in type_map:
            return type_map[rel_type]
        
        # 默认为DEPENDS_ON
        return "DEPENDS_ON"
    
    def _merge_entities(self, entities: List[Dict]) -> List[Dict]:
        """合并重复实体"""
        merged = {}
        
        for entity in entities:
            entity_id = entity["id"]
            
            if entity_id not in merged:
                merged[entity_id] = entity
            else:
                # 合并属性，优先保留已有的非空值
                existing = merged[entity_id]
                for key, value in entity.items():
                    if key not in existing or not existing[key]:
                        existing[key] = value
        
        return list(merged.values())
    
    def _merge_relationships(self, relationships: List[Dict], entities: List[Dict]) -> List[Dict]:
        """合并关系"""
        merged = {}
        entity_ids = {e["id"] for e in entities}
        
        for rel in relationships:
            # 创建关系的唯一键
            key = f"{rel['source_id']}_{rel['type']}_{rel['target_id']}"
            
            # 确保实体存在
            if rel["source_id"] not in entity_ids or rel["target_id"] not in entity_ids:
                continue
            
            if key not in merged:
                merged[key] = rel
            else:
                # 合并描述
                existing = merged[key]
                if rel.get("description") and not existing.get("description"):
                    existing["description"] = rel["description"]
        
        return list(merged.values())
    
    def _extract_global_context(self, document: str, 
                              entities: List[Dict], 
                              relationships: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """提取全局上下文关系（跨块关系）"""
        try:
            # 构建摘要
            summary = f"文档概览：共提取到 {len(entities)} 个实体，{len(relationships)} 个关系。\n"
            summary += "主要实体：\n"
            
            for i, entity in enumerate(entities[:10]):  # 只显示前10个
                summary += f"{i+1}. [{entity['type']}] {entity['name']} (ID: {entity['id']})\n"
            
            messages = [
                {
                    "role": "system",
                    "content": "你是一个需求分析师。请基于以下文档摘要和已提取的实体，识别跨章节的高级关系和全局依赖。"
                },
                {
                    "role": "user",
                    "content": f"文档摘要：{document[:1000]}...\n\n"
                              f"已提取的实体（{len(entities)}个）：\n"
                              f"{summary}\n\n"
                              f"请识别：\n"
                              f"1. 重要的跨模块依赖关系\n"
                              f"2. 高层业务目标与技术实现的关联\n"
                              f"3. 潜在的需求冲突\n"
                              f"4. 需求到系统组件的映射关系\n\n"
                              f"使用相同的JSON格式输出新的关系和可能的实体。"
                }
            ]
            
            response = self.llm.ask_question(messages)
            parsed_data = self._extract_json_from_response(response)
            
            new_entities = self._validate_and_clean_entities(parsed_data.get("entities", []))
            new_relationships = self._validate_and_clean_relationships(
                parsed_data.get("relationships", []),
                entities + new_entities
            )
            
            logger.info(f"全局上下文提取: {len(new_entities)} 个新实体, {len(new_relationships)} 个新关系")
            return new_entities, new_relationships
            
        except Exception as e:
            logger.error(f"提取全局上下文失败: {e}")
            return [], []