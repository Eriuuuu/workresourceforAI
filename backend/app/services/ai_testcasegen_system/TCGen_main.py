import hashlib
# from hashlib import md5
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import pypandoc
import requests
import json
import urllib3
import sseclient
import os
import time
from random import choice
from string import digits,ascii_letters
import re
import io
import tempfile
from docx import Document
from loguru import logger

from app.services.ai_testcasegen_system.TCGen_requirement_parser import RequirementParser
from app.services.ai_testcasegen_system.TCGen_requirement_graph_manager import RequirementGraphManager

class RequirementKnowledgeGraph:
    """需求知识图谱主控制器"""
    
    def __init__(self, llm_system, neo4j_uri: str, neo4j_username: str, neo4j_password: str):
        """
        初始化需求知识图谱系统
        
        Args:
            llm_system: 大模型系统
            neo4j_uri: Neo4j URI
            neo4j_username: Neo4j用户名
            neo4j_password: Neo4j密码
        """
        self.llm_system = llm_system
        
        # 初始化解析器
        self.parser = RequirementParser(llm_system)

        # 初始化图数据库管理器
        self.graph_manager = RequirementGraphManager(
            neo4j_uri, neo4j_username, neo4j_password
        )
        
        # 初始化数据库
        self.graph_manager.initialize_requirement_database()
        
        logger.info("✓ 需求知识图谱系统初始化完成")
    
    def process_requirement_document(self, title: str, content: str, 
                                   metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理需求文档并构建知识图谱
        
        Args:
            title: 文档标题
            content: 文档内容
            metadata: 文档元数据
            
        Returns:
            处理结果
        """
        logger.info(f"开始处理需求文档: {title}")
        
        try:
            # 生成文档ID
            doc_id = self._generate_document_id(title, content)
            
            # 步骤1: 创建文档节点
            doc_node = self.graph_manager.create_requirement_document(
                doc_id, title, content, metadata
            )
            
            if not doc_node:
                return {"success": False, "error": "创建文档节点失败"}
            
            # 步骤2: 解析需求文档
            entities, relationships = self.parser.parse_requirement_document(content)
            
            if not entities:
                return {"success": False, "error": "未提取到任何实体"}
            
            # 步骤3: 构建知识图谱
            stats = self.graph_manager.build_requirement_graph(
                doc_id, entities, relationships
            )
            
            # 步骤4: 生成处理报告
            report = self._generate_processing_report(
                doc_id, title, entities, relationships, stats
            )
            
            logger.info(f"✓ 需求文档处理完成: {title}")
            return {
                "success": True,
                "document_id": doc_id,
                "entities_count": len(entities),
                "relationships_count": len(relationships),
                "stats": stats,
                "report": report
            }
            
        except Exception as e:
            logger.error(f"处理需求文档失败: {e}")
            return {"success": False, "error": str(e)}
    
    def query_related_content(self, query_text: str, query_type: str = "search") -> Dict[str, Any]:
        """
        查询相关知识
        
        Args:
            query_text: 查询文本
            query_type: 查询类型（search/trace/impact/conflict）
            
        Returns:
            查询结果
        """
        logger.info(f"执行查询: {query_text} (类型: {query_type})")
        
        try:
            if query_type == "search":
                # 关键词搜索
                results = self.graph_manager.search_requirements(query_text)
                
            elif query_type == "trace":
                # 需求溯源
                results = self.graph_manager.trace_requirement(query_text)
                
            elif query_type == "impact":
                # 影响分析
                results = self.graph_manager.get_requirement_impact_analysis(query_text)
                
            elif query_type == "conflict":
                # 冲突检测
                results = self.graph_manager.detect_conflicts()
                
            elif query_type == "related":
                # 相关需求
                results = self.graph_manager.find_related_requirements(query_text)
                
            else:
                # 默认使用大模型理解查询意图
                results = self._intelligent_query(query_text)
            
            return {
                "success": True,
                "query": query_text,
                "type": query_type,
                "results": results,
                "count": len(results) if isinstance(results, list) else 1
            }
            
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _intelligent_query(self, query_text: str) -> Dict[str, Any]:
        """使用大模型进行智能查询"""
        try:
            # 使用大模型理解查询意图
            intent_prompt = f"""
            分析以下查询的意图，并返回合适的查询类型：
            查询: {query_text}
            
            可选的查询类型：
            1. search - 关键词搜索（当查询包含一般关键词时）
            2. trace - 需求溯源（当查询包含"溯源"、"来源"、"跟踪"时）
            3. impact - 影响分析（当查询包含"影响"、"依赖"、"关联"时）
            4. conflict - 冲突检测（当查询包含"冲突"、"矛盾"、"不一致"时）
            5. related - 相关需求（当查询包含"相关"、"类似"、"关联"时）
            
            请只返回查询类型，不要解释。
            """
            
            intent_response = self.llm_system.ask_question(intent_prompt)
            query_type = intent_response.strip().lower()
            
            # 提取可能的实体ID
            entity_id = self._extract_entity_id(query_text)
            
            if entity_id:
                # 如果是特定实体的查询
                if query_type in ["trace", "impact", "related"]:
                    return self.query_related_content(entity_id, query_type)
            
            # 否则进行普通搜索
            return self.graph_manager.search_requirements(query_text)
            
        except Exception as e:
            logger.error(f"智能查询失败: {e}")
            return []
    
    def _extract_entity_id(self, text: str) -> Optional[str]:
        """从文本中提取实体ID"""
        # 匹配常见的ID格式：REQ-001, UC-123, US-456等
        import re
        patterns = [
            r'[A-Z]{2,}-\d+',  # REQ-001
            r'#[A-Z]+-\d+',    # #REQ-001
            r'[A-Z]+_\d+',     # REQ_001
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[0]
        
        return None
    
    def _generate_document_id(self, title: str, content: str) -> str:
        """生成文档唯一ID"""
        # 使用标题和内容的哈希值生成ID
        combined = f"{title}_{content[:1000]}"
        hash_obj = hashlib.md5(combined.encode())
        
        # 格式：DOC_哈希前8位
        return f"DOC_{hash_obj.hexdigest()[:16]}"
    
    def _generate_processing_report(self, doc_id: str, title: str, 
                                  entities: List[Dict], relationships: List[Dict],
                                  stats: Dict[str, Any]) -> Dict[str, Any]:
        """生成处理报告"""
        report = {
            "document_id": doc_id,
            "document_title": title,
            "processing_time": datetime.now().isoformat(),
            "summary": {
                "total_entities": len(entities),
                "total_relationships": len(relationships),
                "entity_types": {},
                "relationship_types": {}
            },
            "top_entities": [],
            "critical_relationships": []
        }
        
        # 统计实体类型
        entity_type_count = {}
        for entity in entities:
            entity_type = entity.get("type", "Unknown")
            entity_type_count[entity_type] = entity_type_count.get(entity_type, 0) + 1
        
        report["summary"]["entity_types"] = entity_type_count
        
        # 统计关系类型
        relationship_type_count = {}
        for rel in relationships:
            rel_type = rel.get("type", "Unknown")
            relationship_type_count[rel_type] = relationship_type_count.get(rel_type, 0) + 1
        
        report["summary"]["relationship_types"] = relationship_type_count
        
        # 获取优先级高的实体
        high_priority_entities = [e for e in entities if e.get("priority") == "High"]
        if high_priority_entities:
            report["top_entities"] = high_priority_entities[:5]
        
        # 获取重要关系
        if relationships:
            report["critical_relationships"] = relationships[:5]
        
        # 合并统计信息
        report.update(stats)
        
        return report
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 数据库健康检查
            db_health = self.graph_manager.health_check()
            
            # 获取统计信息
            stats = self.graph_manager.get_requirement_statistics()
            
            return {
                "status": "healthy" if db_health else "unhealthy",
                "database_connected": db_health,
                "statistics": stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def batch_process_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理文档
        
        Args:
            documents: 文档列表，每个文档包含title和content
            
        Returns:
            处理结果列表
        """
        results = []
        
        for i, doc in enumerate(documents):
            logger.info(f"处理文档 {i+1}/{len(documents)}: {doc.get('title', 'Untitled')}")
            
            result = self.process_requirement_document(
                title=doc.get("title", f"Document_{i+1}"),
                content=doc.get("content", ""),
                metadata=doc.get("metadata", {})
            )
            
            results.append({
                "document_index": i,
                "document_title": doc.get("title"),
                **result
            })
        
        return results

async def readdocxfile(file) -> Dict[str, Any]:
    """
    将上传的DOCX文件转换为Markdown格式
    """
    try:
        # 读取文件内容
        contents = await file.read()
        
        # 创建一个临时文件来保存DOCX内容
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name
        
        try:
            # 使用pypandoc转换文件（推荐使用convert_file而不是convert_text）
            markdown_content = pypandoc.convert_file(
                source_file=tmp_file_path,
                to='markdown',
                format='docx',
                extra_args=['--wrap=none']  # 防止自动换行
            )
            
            # 解析Markdown内容，获取元信息
            lines = markdown_content.strip().split('\n')
            
            # 计算段落数（非空行，排除表格、标题、列表标记）
            paragraphs = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('|', '#', '-', '*', '>', '`')):
                    paragraphs.append(line)
            
            # 计算表格数（以|开头的行）
            table_lines = [line for line in lines if line.strip().startswith('|')]
            table_count = 0
            for i, line in enumerate(table_lines):
                if i > 0 and '---' in line:
                    table_count += 1
            
            # 计算图片数
            image_count = sum(1 for line in lines if '![' in line and '](' in line)
            
            # 计算标题数
            heading_count = sum(1 for line in lines if line.strip().startswith('#'))
            
            # 计算列表项数
            list_item_count = sum(1 for line in lines if line.strip().startswith(('-', '*', '+', '1.', '2.', '3.')))
            
            # 清理markdown内容（可选：移除多余的空行）
            cleaned_markdown = '\n'.join([line.rstrip() for line in lines])

            return {
                "success": True,
                "raw_content": cleaned_markdown,
                "format": "markdown",
                "metadata": {
                    "paragraph_count": len(paragraphs),
                    "table_count": table_count,
                    "image_count": image_count,
                    "heading_count": heading_count,
                    "list_item_count": list_item_count,
                    "total_characters": len(cleaned_markdown),
                    "total_words": len(cleaned_markdown.split()),
                    "line_count": len(lines),
                    "file_name": file.filename,
                    "file_size": len(contents)
                },
                "conversion_messages": ["使用pypandoc转换完成"]
            }
            
        finally:
            # 确保删除临时文件
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"解析DOCX文件失败: {str(e)}"
        }
        

class IntegrateGlodonTestcasegenWorkflow:
    def __init__(self,token:str, entities: List):
        self.token = token
        self.entities = entities

    def doc_to_markdown_string(self, doc_path):
        """
        将doc/docx文件转换为markdown字符串
        """
        try:
            # 使用pandoc进行转换
            output = pypandoc.convert_file(doc_path, 'md', format='docx')
            return output
        except Exception as e:
            return f"转换出错: {str(e)}"


    # ###############上传文件并获得URL###############
    # def upload_files(self, basetoken, uploadurl,filepath):
    #     with open(filepath, "rb") as f:
    #         files = {"file": f}
    #         data  = {"purpose": "infer"}
    #         headers = {"Authorization": basetoken}
    #         response = requests.post(uploadurl, files=files, data=data, headers=headers)
    #     if response.status_code == 200:
    #         res = response.json()
    #         if res["code"] != 200:
    #             raise Exception(res["message"])

    #         file_url= res["data"]["url"]
    #         print(file_url)
    #         return file_url
    #     else:
    #         raise Exception(response.status_code)


    ###############异步调用workflow###############

    def get_result(self, pid, auth):
        query_url = "https://copilot.glodon.com/api/cvforce/workflow/v1/process"
        header = {"Authorization": auth}
        res = requests.get(f"{query_url}/{pid}", headers=header)
        return res

    def get_node_result(self, pid, node_id, auth):
        query_url = "https://copilot.glodon.com/api/cvforce/workflow/v1/process"
        header = {"Authorization": auth}
        res = requests.get(f"{query_url}/{pid}/node/{node_id}", headers=header)
        return res

    def workflow_apply_async_requirementsgen(self, requirement_string,api_string,workflow_URL, workflowtoken):
        payload ={
            "requirement_string": str(requirement_string),
            "api_string": [str(api_string)]
        }

        header ={
            "Content-Type": "application/json",
            "Authorization": str(workflowtoken),
            "Async": "on"
        }
        response = requests.post(workflow_URL,data=json.dumps(payload),headers=header)
        return response


    def workflow_apply_async_testcasesgen(self, cases: dict ,requirementdoc: str, modulename: str, workflow_URL: str, workflowtoken: str):
        payload ={
            "requirement_cases": cases,
            "requirement_doc": requirementdoc,
            "module_name": modulename,
        }

        header ={
            "Content-Type": "application/json",
            "Authorization": str(workflowtoken),
            "Async": "on"
        }
        response = requests.post(workflow_URL,data=json.dumps(payload),headers=header)
        return response

    def get_end_node_id(self, base_token : str,processid:str, timeperiod: int = 1000 ,interval :int = 5):
        end_node_id= ''
        for i in range(timeperiod):
            response = self.get_result(processid, base_token)
            
            if response.status_code != 200:
                print("获取工作流过程状态失败：", response.status_code, response.text)
                break

            res = response.json()
            print(res)
            data = res.get("data") or {}

            if data.get("status") == "SUCCESS":
                end_node_id = res["data"]["results"][-1].get("nodeId")
                return end_node_id
            elif data.get("status") == "FAILED":
                end_node_id = res["data"]["results"][-1].get("nodeId")
                return end_node_id
            time.sleep(interval)
        return None


    def clean_and_parse_json(self, raw_text):
        match = re.search(r'\[.*\]', raw_text, flags=re.S)
        if match:
            json_str = match.group()
            print(json_str)
            data = json.loads(json_str)
            # print(json.dumps(data, ensure_ascii=False, indent=2))
            return data
        else:
            print("未找到 JSON 段落")
            return None

    # #万能取值器,
    # def safe_get(self, obj, *keys, default=None):
    #     """
    #     万能取值：
    #     - 遇到 dict 用 .get
    #     - 遇到 list 就用索引 0，再递归
    #     """
    #     for k in keys:
    #         if isinstance(obj, list) and obj:
    #             obj = obj[0]
    #         if isinstance(obj, dict):
    #             obj = obj.get(k, default)
    #         else:
    #             return default
    #     return obj
    def process_entities(self):
        description =[]
        for entity in self.entities:
            rule = entity["name"] +": "+ entity["description"]
            description.append(rule)
            result = '。'.join(description)
        return result


    def excute_test_gen(self, requirements_markdown_string, api_markdown_string):
        #文本处理
        # api_docx_path= "E://RunTestZK//tests//AI测试材料准备//2025hackathon//material//获取当前登录人有权限的指定组织的子节点.docx"
        # requirement_docx_path ="E://RunTestZK//tests//AI测试材料准备//2025hackathon//material//获取当前登录人有权限的指定组织的子节点_需求.docx"
        # api_markdown_string = self.doc_to_markdown_string(api_docx_path)
        # requirements_markdown_string = self.doc_to_markdown_string(requirement_docx_path)

        ##异步调用工作流-需求点生成
        workflow_id ="ff1d44be-c7a3-400b-bfbb-833cbee1a469"
        workflow_URL = f"https://copilot.glodon.com/api/cvforce/workflow/v1/flowApi/{workflow_id}/process"
        
        response = self.workflow_apply_async_requirementsgen(requirements_markdown_string, api_markdown_string,workflow_URL, self.token) 
        pid = response.json().get("data", "")
        end_nodeod = self.get_end_node_id(self.token,pid,1000,10)
        print(end_nodeod)
        output_flowone =[]
        if end_nodeod.startswith("End"):
            response_of_flowone = self.get_node_result(pid, end_nodeod, self.token)
            response_data= response_of_flowone.json()

            print("-----------------需求点分堆-----------------------")
            output_data_requirementcases = response_data['data']['result']['data']['outputs']['output']
            requirement_stacks = self.clean_and_parse_json(output_data_requirementcases)
            output_flowone.append(requirement_stacks)

            print("-----------------需求文档-----------------------")
            output_data_requirement = response_data['data']['result']['data']['outputs']['output2']
            output_flowone.append(output_data_requirement)
            with open("output_requirement_stacks.json", "w", encoding="utf-8") as f:
                json.dump(requirement_stacks, f, ensure_ascii=False, indent=4)
        else:
            print("工作流运行失败")
            response_flowone_warning = self.get_node_result(pid, end_nodeod, self.token)
            response_data= response_flowone_warning.json()
            print(json.dumps(response_flowone_warning.json(), indent=2, ensure_ascii=False))

        ##异步调用工作流-测试点生成
        if len(output_flowone)!=0:
            tastcasesgen_workflowid = "14d28af1-3e44-467d-a9b2-9c7f3446025f"
            tastcasesgen_url = f"https://copilot.glodon.com/api/cvforce/workflow/v1/flowApi/{tastcasesgen_workflowid}/process"
            case_results = []
            countnum = 0
            stacks =output_flowone[0]
            for stack in stacks:
                for case in stack["requirements"]:
                    testcasesgen_response = self.workflow_apply_async_testcasesgen(case,str(output_flowone[1]),stack["module"],tastcasesgen_url,self.token)
                    testcasesgen_pid = testcasesgen_response.json().get("data", "")
                    testcasesgen_end_nodeod = self.get_end_node_id(self.token,testcasesgen_pid,1000,10)
                    if testcasesgen_end_nodeod.startswith("End"):
                        testcasesgen_response2 = self.get_node_result(testcasesgen_pid, testcasesgen_end_nodeod, self.token)
                        testcase_data = testcasesgen_response2.json()
                        testcase_cases = testcase_data['data']['result']['data']['outputs']['testcases']
                        countnum +=1
                        print(f"-----------------{countnum}-----------------------")
                        testcase_cases_list = self.clean_and_parse_json(testcase_cases)                 
                        case_results.extend(testcase_cases_list)
            
            with open("output_testcase_1.json", "w", encoding="utf-8") as f:
                json.dump(case_results, f, ensure_ascii=False, indent=4)
            return case_results
        return False