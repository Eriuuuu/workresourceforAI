from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, File, UploadFile
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
import json
import asyncio
import threading
import time as _time
from datetime import datetime
from loguru import logger

from app.services.ai_code_qa_system.main_system import LangChainCodeQASystem
from app.core.config_for_ai_service import get_config_manager
from app.models.ai_system_model import (
    ParseDocumentResponse, TestCaseGenRequest, TestCaseGenResponse,
    GraphNodeData, GraphEdgeData, TestCaseItem, TestCaseStep,
    SubmitTaskRequest, SubmitTaskResponse, TaskStatusResponse,
    InitializeRequest, InitializeResponse, QuestionRequest, QuestionResponse,
    SessionInfo, SystemStatus, DebugRetrievalRequest, DebugRetrievalResponse,
)
from app.services.ai_testcasegen_system.TCGen_base_glodon_llm import GlodonBaseLLM
from app.services.ai_code_qa_system.glodon_api_token import get_glodon_token
from app.services.ai_testcasegen_system.TCGen_main import (
    RequirementKnowledgeGraph, IntegrateGlodonTestcasegenWorkflow, readdocxfile,
)


# ==================== 路由与全局状态 ====================
router = APIRouter()
_qa_system_instance = None
_active_sessions: Dict[str, Dict[str, Any]] = {}


# ==================== 异步任务管理 ====================
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


# ==================== 共享业务逻辑（消除重复） ====================

_PRIORITY_MAP = {
    "高": "高", "中": "中", "低": "低",
    "High": "高", "Medium": "中", "Low": "低",
    "P0": "高", "P1": "高", "P2": "中", "P3": "低",
}


def _create_doc_processor() -> RequirementKnowledgeGraph:
    """创建文档处理器实例（工厂函数，消除重复初始化代码）"""
    config = get_config_manager()
    llm_instance = GlodonBaseLLM(config, get_glodon_token())
    return RequirementKnowledgeGraph(
        llm_instance,
        config.db.neo4j_uri,
        config.db.neo4j_username,
        config.db.neo4j_password,
    )


def _convert_raw_steps(raw_steps: Any) -> List[Dict[str, str]]:
    """将后端工作流返回的各种 steps 格式统一为 [{action, expected}]"""
    steps: List[Dict[str, str]] = []
    if not raw_steps:
        return steps
    # 工作流返回的 testSteps 是带编号的文本字符串（如 "1. xxx\n2. yyy"）
    if isinstance(raw_steps, str):
        for line in raw_steps.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # 去掉开头的编号（如 "1. "、"1、"、"Step 1:"）
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
    """将工作流原始用例结果转换为标准格式（兼容多种字段命名）"""
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
    """从需求文本生成文档标题"""
    title = requirement_text[:100].replace("\n", " ").strip()
    return title if len(title) >= 10 else "需求文档"


def _build_search_keyword(search_keyword: str, requirement_text: str) -> str:
    """构建图谱检索关键词"""
    keyword = search_keyword.strip()
    if keyword:
        return keyword
    return requirement_text[:50].replace("\n", " ").strip()


def _extract_entities_string(entities: List[Dict]) -> str:
    """将实体列表拼接为描述字符串，供工作流使用"""
    descriptions = []
    for entity in entities:
        if isinstance(entity, dict):
            name = entity.get("name", "")
            desc = entity.get("description", "")
            if name:
                descriptions.append(f"{name}: {desc}" if desc else name)
    return "。".join(descriptions)


# ==================== 文档解析 + 图谱构建（共享核心） ====================

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
    """
    核心业务逻辑：解析文档 → 构建图谱 → 读取节点/边。
    返回 {"success", "message", "graph_nodes", "graph_edges", "processing_time", "error?}
    """
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

    # 从图数据库读取节点和边
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
    """
    核心业务逻辑：检索图谱 → 调用工作流 → 转换用例结果。
    返回 {"success", "message", "test_cases", "processing_time", "error?}
    """
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


# ==================== 后台任务执行（供 submit-task 调用） ====================

def _run_parse_graph_task(task_id: str, requirement_text: str, search_keyword: str):
    """后台线程：执行文档解析+图谱构建"""
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
    """后台线程：执行用例生成"""
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


# ==================== 依赖注入 ====================

def get_config():
    return get_config_manager()


def get_qa_system() -> LangChainCodeQASystem:
    global _qa_system_instance
    if _qa_system_instance is None:
        raise HTTPException(status_code=503, detail="QA系统未初始化，请先调用/initialize接口")
    return _qa_system_instance


def get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _active_sessions:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return _active_sessions[session_id]


# ==================== AI 问答系统接口 ====================

@router.post("/initialize", response_model=InitializeResponse, summary="初始化AI问答系统")
async def initialize_system(request: InitializeRequest):
    global _qa_system_instance
    try:
        config = get_config()
        _qa_system_instance = LangChainCodeQASystem(config)
        await asyncio.to_thread(_qa_system_instance.initialize, force_rebuild=request.force_rebuild)
        system_stats = await asyncio.to_thread(_qa_system_instance.get_system_status)
        return InitializeResponse(
            success=True,
            message="AI问答系统初始化成功",
            system_id=str(uuid.uuid4()),
            initialization_time=datetime.now().isoformat(),
            stats=system_stats,
        )
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"系统初始化失败: {str(e)}")


@router.post("/ask", response_model=QuestionResponse, summary="提问")
async def ask_question(request: QuestionRequest, qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        if session_id not in _active_sessions:
            _active_sessions[session_id] = {
                'created_at': datetime.now().isoformat(),
                'question_count': 0,
                'last_active': datetime.now().isoformat(),
            }
        session = _active_sessions[session_id]
        session['last_active'] = datetime.now().isoformat()

        result = await asyncio.to_thread(qa_system.ask_question, request.question)
        session['question_count'] += 1

        return QuestionResponse(
            success=result.get('success', False),
            answer=result.get('answer'),
            question=request.question,
            session_id=session_id,
            source_files=result.get('source_files', []),
            files_count=result.get('files_count', 0),
            token_usage=result.get('token_usage'),
            processing_time=result.get('processing_time', 0),
            error=result.get('error'),
        )
    except Exception as e:
        logger.error(f"提问接口出错: {e}")
        raise HTTPException(status_code=500, detail=f"处理问题失败: {str(e)}")


# ==================== 用例生成系统接口 ====================

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
    """同步接口：解析文档 → 构建图谱，通过 asyncio.to_thread 异步执行不阻塞事件循环"""
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
    """同步接口：检索图谱 → 生成用例，通过 asyncio.to_thread 异步执行不阻塞事件循环"""
    try:
        result = await asyncio.to_thread(_execute_generate_cases, request.requirement_text, request.search_keyword)

        test_cases = [TestCaseItem(steps=[TestCaseStep(**s) for s in c["steps"]], **{k: v for k, v in c.items() if k != "steps"}) for c in result["test_cases"]]

        return TestCaseGenResponse(
            success=result["success"],
            message=result["message"],
            test_cases=test_cases,
            processing_time=result["processing_time"],
        )
    except Exception as e:
        logger.error(f"生成测试用例失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"用例生成失败: {str(e)}")


# ==================== 异步任务接口（推荐使用，支持页签切换） ====================

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
    t = threading.Thread(
        target=func,
        args=(task_id, request.requirement_text, request.search_keyword),
        daemon=True,
    )
    t.start()

    logger.info(f"异步任务已提交: task_id={task_id}, type={request.task_type}")
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


# ==================== 会话与系统管理接口 ====================

@router.get("/sessions/{session_id}", response_model=SessionInfo, summary="获取会话信息")
async def get_session_info(session_id: str, qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        session = get_session(session_id)
        system_status = await asyncio.to_thread(qa_system.get_system_status)
        return SessionInfo(
            session_id=session_id,
            created_at=session['created_at'],
            last_active=session['last_active'],
            question_count=session['question_count'],
            conversation_history_count=0,
            system_status=system_status,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[SessionInfo], summary="获取所有活跃会话")
async def get_all_sessions(qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        system_status = await asyncio.to_thread(qa_system.get_system_status)
        sessions_info = [
            SessionInfo(
                session_id=sid,
                created_at=s['created_at'],
                last_active=s['last_active'],
                question_count=s['question_count'],
                conversation_history_count=0,
                system_status=system_status,
            )
            for sid, s in _active_sessions.items()
        ]
        return sessions_info
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(session_id: str):
    try:
        if session_id in _active_sessions:
            del _active_sessions[session_id]
            return {"success": True, "message": f"会话 {session_id} 已删除"}
        raise HTTPException(status_code=404, detail="会话不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SystemStatus, summary="系统状态检查")
async def get_system_status(qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        system_status = await asyncio.to_thread(qa_system.get_system_status)
        return SystemStatus(
            initialized=system_status.get('initialized', False),
            initialization_time=system_status.get('initialization_time'),
            codebase_info=system_status.get('codebase'),
            vector_database_stats=system_status.get('vector_database'),
            graph_database_stats=system_status.get('graph_database'),
            active_sessions=len(_active_sessions),
            system_stats=system_status.get('system_stats'),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/debug/retrieval", response_model=DebugRetrievalResponse, summary="调试检索")
async def debug_retrieval(request: DebugRetrievalRequest, qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        start_time = _time.time()
        debug_result = await asyncio.to_thread(qa_system.debug_retrieval, request.question)

        retrieved_files = []
        for doc in debug_result.get('retrieved_documents', []):
            content = doc.get('content', '')
            retrieved_files.append({
                'file_path': doc.get('file_path', '未知'),
                'similarity': doc.get('similarity', 0),
                'content_preview': content[:200] + '...' if len(content) > 200 else content,
                'metadata': doc.get('metadata', {}),
            })

        return DebugRetrievalResponse(
            question=request.question,
            retrieved_files=retrieved_files,
            count=len(retrieved_files),
            processing_time=_time.time() - start_time,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear", summary="清空对话历史")
async def clear_conversation_history(qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        await asyncio.to_thread(qa_system.clear_conversation_history)
        return {"success": True, "message": "对话历史已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild-index", summary="重建索引")
async def rebuild_index(qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        await asyncio.to_thread(qa_system.rebuild_index)
        return {"success": True, "message": "索引重建完成", "time": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="健康检查")
async def health_check():
    try:
        system_ok = _qa_system_instance is not None and _qa_system_instance.is_initialized
        health_data = {
            "status": "healthy" if system_ok else "unhealthy",
            "service": "AI智能代理API",
            "timestamp": datetime.now().isoformat(),
            "system_initialized": system_ok,
            "active_sessions": len(_active_sessions),
            "version": "1.0.0",
        }
        return JSONResponse(content=health_data, status_code=200 if system_ok else 503)
    except Exception as e:
        return JSONResponse(
            content={"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()},
            status_code=503,
        )


@router.get("/config", summary="获取配置")
async def get_configuration(qa_system: LangChainCodeQASystem = Depends(get_qa_system)):
    try:
        config = qa_system.config
        return {
            "codebase_path": config.system.codebase_path,
            "chunk_size": config.system.chunk_size,
            "chunk_overlap": config.system.chunk_overlap,
            "max_files_per_query": config.system.max_files_per_query,
            "llm_model": config.api.glodonai_llm_model,
            "vector_store_path": config.db.chroma_persist_dir,
            "neo4j_uri": config.db.neo4j_uri,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", summary="API根路径")
async def api_root():
    return {
        "name": "AI代码智能问答系统API",
        "version": "1.0.0",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/aiagent/initialize", "description": "初始化系统"},
            {"method": "POST", "path": "/api/v1/aiagent/ask", "description": "提问"},
            {"method": "POST", "path": "/api/v1/aiagent/getdocx", "description": "上传解析文档"},
            {"method": "POST", "path": "/api/v1/aiagent/parse-and-build-graph", "description": "解析文档构建图谱"},
            {"method": "POST", "path": "/api/v1/aiagent/gentestcases", "description": "生成测试用例"},
            {"method": "POST", "path": "/api/v1/aiagent/submit-task", "description": "提交异步任务"},
            {"method": "GET",  "path": "/api/v1/aiagent/task-status/{task_id}", "description": "查询任务状态"},
            {"method": "GET",  "path": "/api/v1/aiagent/status", "description": "系统状态"},
            {"method": "GET",  "path": "/api/v1/aiagent/health", "description": "健康检查"},
        ],
        "documentation": "/docs",
        "openapi_schema": "/openapi.json",
    }
