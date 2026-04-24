"""
测试用例生成系统 API — 独立路由，与智能问答系统解耦
"""
from fastapi import APIRouter, HTTPException, File, UploadFile
from typing import Optional, Dict, Any, List
import uuid
import asyncio
import threading
import time as _time
from datetime import datetime
from loguru import logger

from app.core.config_for_ai_service import get_config_manager
from app.core.glodon_api_token import get_glodon_token
from app.models.ai_system_model import (
    ParseDocumentResponse, TestCaseGenRequest, TestCaseGenResponse,
    GraphNodeData, GraphEdgeData, TestCaseItem, TestCaseStep,
    SubmitTaskRequest, SubmitTaskResponse, TaskStatusResponse,
)
from app.services.ai_testcasegen_system.TCGen_base_glodon_llm import GlodonBaseLLM
from app.services.ai_testcasegen_system.TCGen_main import (
    RequirementKnowledgeGraph, IntegrateGlodonTestcasegenWorkflow, readdocxfile,
)


# ==================== 路由与全局状态 ====================
router = APIRouter()

_task_store: Dict[str, Dict[str, Any]] = {}
_task_store_lock = threading.Lock()


def _safe_get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with _task_store_lock:
        return _task_store.get(task_id)


def _safe_update_task(task_id: str, updates: Dict[str, Any]):
    with _task_store_lock:
        if task_id in _task_store:
            _task_store[task_id].update(updates)
            _task_store[task_id]["updated_at"] = datetime.now().isoformat()


def _safe_create_task(task_id: str, task_info: Dict[str, Any]):
    with _task_store_lock:
        _task_store[task_id] = task_info


# ==================== 业务辅助函数 ====================

_PRIORITY_MAP = {
    "高": "高", "中": "中", "低": "低",
    "High": "高", "Medium": "中", "Low": "低",
    "P0": "高", "P1": "高", "P2": "中", "P3": "低",
}


def _create_doc_processor() -> RequirementKnowledgeGraph:
    """创建文档处理器实例"""
    config = get_config_manager()
    llm_instance = GlodonBaseLLM(config, get_glodon_token())
    return RequirementKnowledgeGraph(
        llm_instance,
        config.db.neo4j_uri,
        config.db.neo4j_username,
        config.db.neo4j_password,
    )


def _convert_raw_steps(raw_steps: Any) -> List[Dict[str, str]]:
    """将工作流返回的各种 steps 格式统一为 [{action, expected}]"""
    steps: List[Dict[str, str]] = []
    if not raw_steps:
        return steps
    if isinstance(raw_steps, str):
        for line in raw_steps.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            import re
            cleaned = re.sub(r'^[\d]+[\.\、\)\]:]\s*', '', line).strip()
            if cleaned:
                steps.append({"action": cleaned})
        return steps
    if not isinstance(raw_steps, list):
        return steps
    for step in raw_steps:
        if isinstance(step, dict):
            steps.append({
                "action": step.get("action", step.get("step", "")),
                "expected": step.get("expected", step.get("expected_result", step.get("expectResult", ""))),
            })
        elif isinstance(step, str):
            steps.append({"action": step})
    return steps


def _convert_case_results(case_results: List[Dict]) -> List[Dict[str, Any]]:
    """将工作流原始用例结果转换为标准格式"""
    test_cases = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for idx, case in enumerate(case_results):
        if not isinstance(case, dict):
            continue
        raw_priority = str(case.get("priority", case.get("level", "中")))
        test_cases.append({
            "id": case.get("testcase_id", case.get("id", f"TC{idx + 1:03d}")),
            "name": case.get("summary", case.get("name", case.get("title", f"测试用例{idx + 1}"))),
            "description": case.get("description", case.get("desc", "")),
            "priority": _PRIORITY_MAP.get(raw_priority, "中"),
            "preconditions": case.get("preconditions", case.get("pre_condition", "")),
            "steps": _convert_raw_steps(case.get("testSteps", case.get("steps", case.get("test_steps", [])))),
            "expected_result": case.get("expectResult", ""),
            "target_api": case.get("targetAPI", ""),
            "module": case.get("module", ""),
            "status": "未执行",
            "created_at": now_str,
            "updated_at": now_str,
        })
    return test_cases


def _build_graph_title(requirement_text: str) -> str:
    title = requirement_text[:100].replace("\n", " ").strip()
    return title if len(title) >= 10 else "需求文档"


def _build_search_keyword(search_keyword: str, requirement_text: str) -> str:
    keyword = search_keyword.strip()
    if keyword:
        return keyword
    return requirement_text[:50].replace("\n", " ").strip()


def _extract_entities_string(entities: List[Dict]) -> str:
    descriptions = []
    for entity in entities:
        if isinstance(entity, dict):
            name = entity.get("name", "")
            desc = entity.get("description", "")
            if name:
                descriptions.append(f"{name}: {desc}" if desc else name)
    return "。".join(descriptions)


# ==================== 核心业务逻辑 ====================

_NODE_QUERY = """
MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(e)
RETURN e.id as id, e.name as name, e.type as type,
       e.description as description, labels(e) as labels
LIMIT 200
"""

_EDGE_QUERY = """
MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(e1)-[r]->(e2)
WHERE exists((d)-[:CONTAINS]->(e2))
RETURN e1.id as source, e2.id as target, type(r) as label,
       r.description as description
LIMIT 300
"""


def _execute_parse_graph(requirement_text: str, search_keyword: str) -> Dict[str, Any]:
    start = _time.time()
    doc_processor = _create_doc_processor()
    title = _build_graph_title(requirement_text)

    result = doc_processor.process_requirement_document(title, requirement_text)
    elapsed = _time.time() - start

    if not result.get("success"):
        return {
            "success": False,
            "message": result.get("error", "文档解析失败"),
            "graph_nodes": [],
            "graph_edges": [],
            "processing_time": elapsed,
            "error": result.get("error"),
        }

    doc_id = result["document_id"]
    graph_nodes: List[Dict] = []
    graph_edges: List[Dict] = []

    try:
        gm = doc_processor.graph_manager
        for record in gm.graph.run(_NODE_QUERY, doc_id=doc_id).data():
            labels = record.get("labels", [])
            graph_nodes.append({
                "id": record.get("id", ""),
                "name": record.get("name", ""),
                "label": labels[0] if labels else "Requirement",
                "type": record.get("type", "requirement"),
                "description": record.get("description", ""),
            })

        for record in gm.graph.run(_EDGE_QUERY, doc_id=doc_id).data():
            graph_edges.append({
                "source": record.get("source", ""),
                "target": record.get("target", ""),
                "label": record.get("label", "关联"),
                "properties": {"description": record.get("description", "")},
            })
    except Exception as e:
        logger.warning(f"读取图谱数据失败: {e}")

    return {
        "success": True,
        "message": f"文档解析完成，提取 {result.get('entities_count', 0)} 个实体、{result.get('relationships_count', 0)} 个关系",
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "processing_time": elapsed,
    }


def _execute_generate_cases(requirement_text: str, search_keyword: str) -> Dict[str, Any]:
    start = _time.time()
    doc_processor = _create_doc_processor()
    keyword = _build_search_keyword(search_keyword, requirement_text)

    research_result = doc_processor.query_related_content(keyword, "search")
    entities = research_result.get("results", [])

    if not entities:
        return {
            "success": False,
            "message": "图谱中未检索到相关内容，请先解析文档构建知识图谱",
            "test_cases": [],
            "processing_time": _time.time() - start,
        }

    entities_string = _extract_entities_string(entities)
    token = get_glodon_token()
    workflow = IntegrateGlodonTestcasegenWorkflow(token, entities)
    case_results = workflow.excute_test_gen(requirement_text, entities_string)
    elapsed = _time.time() - start

    if not case_results:
        return {
            "success": False,
            "message": "测试用例生成失败，工作流未返回有效结果",
            "test_cases": [],
            "processing_time": elapsed,
        }

    test_cases = _convert_case_results(case_results)
    return {
        "success": True,
        "message": f"成功生成 {len(test_cases)} 条测试用例",
        "test_cases": test_cases,
        "processing_time": elapsed,
    }


# ==================== 后台任务 ====================

def _run_parse_graph_task(task_id: str, requirement_text: str, search_keyword: str):
    try:
        _safe_update_task(task_id, {"status": "processing"})
        result = _execute_parse_graph(requirement_text, search_keyword)
        if not result["success"]:
            _safe_update_task(task_id, {"status": "failed", "error": result.get("error", "文档解析失败")})
            return
        _safe_update_task(task_id, {"status": "completed", "result": result})
    except Exception as e:
        logger.error(f"任务 {task_id} 图谱构建失败: {e}", exc_info=True)
        _safe_update_task(task_id, {"status": "failed", "error": str(e)})


def _run_generate_cases_task(task_id: str, requirement_text: str, search_keyword: str):
    try:
        _safe_update_task(task_id, {"status": "processing"})
        result = _execute_generate_cases(requirement_text, search_keyword)
        if not result["success"]:
            _safe_update_task(task_id, {"status": "failed", "error": result["message"]})
            return
        _safe_update_task(task_id, {"status": "completed", "result": result})
    except Exception as e:
        logger.error(f"任务 {task_id} 用例生成失败: {e}", exc_info=True)
        _safe_update_task(task_id, {"status": "failed", "error": str(e)})


# ==================== 路由接口 ====================

@router.post("/getdocx", response_model=ParseDocumentResponse, summary="获取文档")
async def get_docx(file: UploadFile = File(...)):
    """解析上传的DOCX文件为文本"""
    res = await readdocxfile(file)
    if res and res.get("success"):
        return ParseDocumentResponse(
            success=True,
            raw_content=res.get("raw_content", ""),
            format=res.get("format", "markdown"),
            metadata=res.get("metadata", {}),
        )
    error_msg = res.get("error", "未知错误") if res else "文件解析失败"
    return ParseDocumentResponse(success=False, error=error_msg)


@router.post("/parse-and-build-graph",
             response_model=TestCaseGenResponse,
             summary="解析文档并构建知识图谱（同步）")
async def parse_and_build_graph(request: TestCaseGenRequest):
    """同步接口：解析文档 → 构建图谱"""
    try:
        result = await asyncio.to_thread(_execute_parse_graph, request.requirement_text, request.search_keyword)
        graph_nodes = [GraphNodeData(**n) for n in result["graph_nodes"]]
        graph_edges = [GraphEdgeData(**e) for e in result["graph_edges"]]
        return TestCaseGenResponse(
            success=result["success"],
            message=result["message"],
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
            processing_time=result["processing_time"],
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"解析文档构建图谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/gentestcases",
             response_model=TestCaseGenResponse,
             summary="基于知识图谱生成测试用例（同步）")
async def generate_test_cases(request: TestCaseGenRequest):
    """同步接口：检索图谱 → 生成用例"""
    try:
        result = await asyncio.to_thread(_execute_generate_cases, request.requirement_text, request.search_keyword)
        test_cases = [
            TestCaseItem(
                steps=[TestCaseStep(**s) for s in c["steps"]],
                **{k: v for k, v in c.items() if k != "steps"}
            ) for c in result["test_cases"]
        ]
        return TestCaseGenResponse(
            success=result["success"],
            message=result["message"],
            test_cases=test_cases,
            processing_time=result["processing_time"],
        )
    except Exception as e:
        logger.error(f"生成测试用例失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"用例生成失败: {str(e)}")


@router.post("/submit-task",
             response_model=SubmitTaskResponse,
             summary="提交异步任务",
             description="提交文档解析或用例生成任务，后台执行，支持页签切换不中断")
async def submit_task(request: SubmitTaskRequest):
    """提交异步任务，立即返回 task_id，前端可轮询状态"""
    task_id = str(uuid.uuid4())[:8]
    now_str = datetime.now().isoformat()

    _safe_create_task(task_id, {
        "task_id": task_id,
        "task_type": request.task_type,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_str,
        "updated_at": now_str,
    })

    task_funcs = {
        "parse_graph": (_run_parse_graph_task, "文档解析任务已提交"),
        "generate_cases": (_run_generate_cases_task, "用例生成任务已提交"),
    }
    if request.task_type not in task_funcs:
        raise HTTPException(status_code=400, detail=f"不支持的任务类型: {request.task_type}")

    func, message = task_funcs[request.task_type]
    t = threading.Thread(target=func, args=(task_id, request.requirement_text, request.search_keyword), daemon=True)
    t.start()

    logger.info(f"用例生成异步任务已提交: task_id={task_id}, type={request.task_type}")
    return SubmitTaskResponse(task_id=task_id, status="pending", message=message)


@router.get("/task-status/{task_id}",
            response_model=TaskStatusResponse,
            summary="查询任务状态")
async def get_task_status(task_id: str):
    """根据 task_id 查询异步任务的执行状态和结果"""
    task = _safe_get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或已过期")

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        task_type=task.get("task_type", ""),
        result=task.get("result"),
        error=task.get("error"),
        created_at=task.get("created_at"),
        updated_at=task.get("updated_at"),
    )


@router.get("/", summary="API根路径")
async def api_root():
    return {
        "name": "AI测试用例生成系统API",
        "version": "1.0.0",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/testcase/getdocx", "description": "上传并解析DOCX文件"},
            {"method": "POST", "path": "/api/v1/testcase/parse-and-build-graph", "description": "解析文档并构建知识图谱"},
            {"method": "POST", "path": "/api/v1/testcase/gentestcases", "description": "生成测试用例"},
            {"method": "POST", "path": "/api/v1/testcase/submit-task", "description": "提交异步任务"},
            {"method": "GET",  "path": "/api/v1/testcase/task-status/{task_id}", "description": "查询任务状态"},
        ],
    }
