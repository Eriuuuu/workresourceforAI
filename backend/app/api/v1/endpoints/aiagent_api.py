"""
智能问答系统 API — 独立路由，与用例生成系统解耦
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
import asyncio
import threading
import time as _time
from datetime import datetime
from loguru import logger

from app.services.ai_code_qa_system.main_system import LangChainCodeQASystem
from app.services.agents.qa_system_manager import init_qa_system as register_qa_instance
from app.core.config_for_ai_service import get_config_manager
from app.models.ai_system_model import (
    SubmitTaskResponse, TaskStatusResponse,
    InitializeRequest, QuestionRequest,
    SessionInfo, SystemStatus, DebugRetrievalRequest, DebugRetrievalResponse,
    ChatRequest, ChatStatusResponse, AgentInfo,
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


# ==================== 后台任务执行 ====================

def _run_initialize_task(task_id: str, force_rebuild: bool):
    """后台线程：执行系统初始化"""
    global _qa_system_instance
    try:
        _safe_update_task(task_id, {"status": "processing"})
        config = get_config()
        _qa_system_instance = LangChainCodeQASystem(config)
        _qa_system_instance.initialize(force_rebuild=force_rebuild)
        # 注册到 qa_system_manager，供 qa_agent 获取（解耦循环引用）
        register_qa_instance(_qa_system_instance)
        system_stats = _qa_system_instance.get_system_status()
        _safe_update_task(task_id, {
            "status": "completed",
            "result": {
                "success": True,
                "message": "AI问答系统初始化成功",
                "system_id": str(uuid.uuid4()),
                "initialization_time": datetime.now().isoformat(),
                "stats": system_stats,
            },
        })
    except Exception as e:
        logger.error(f"初始化任务 {task_id} 失败: {e}", exc_info=True)
        _safe_update_task(task_id, {"status": "failed", "error": str(e)})


def _run_ask_task(task_id: str, question: str, session_id: str):
    """后台线程：执行AI问答（老系统兼容接口）"""
    global _qa_system_instance, _active_sessions
    try:
        _safe_update_task(task_id, {"status": "processing"})

        if _qa_system_instance is None or not _qa_system_instance.is_initialized:
            _safe_update_task(task_id, {"status": "failed", "error": "QA系统未初始化，请先调用/initialize接口"})
            return

        if session_id not in _active_sessions:
            _active_sessions[session_id] = {
                'created_at': datetime.now().isoformat(),
                'question_count': 0,
                'last_active': datetime.now().isoformat(),
            }
        _active_sessions[session_id]['last_active'] = datetime.now().isoformat()

        result = _qa_system_instance.ask_question(question)
        _active_sessions[session_id]['question_count'] += 1

        _safe_update_task(task_id, {
            "status": "completed",
            "result": {
                "success": result.get('success', False),
                "answer": result.get('answer'),
                "question": question,
                "session_id": session_id,
                "source_files": result.get('source_files', []),
                "files_count": result.get('files_count', 0),
                "token_usage": result.get('token_usage'),
                "processing_time": result.get('processing_time', 0),
                "error": result.get('error'),
            },
        })
    except Exception as e:
        logger.error(f"问答任务 {task_id} 失败: {e}", exc_info=True)
        _safe_update_task(task_id, {"status": "failed", "error": str(e)})


async def _run_chat_task(task_id: str, message: str, session_id: str, agent_role: Optional[str]):
    """异步后台任务：执行多 Agent 聊天任务"""
    try:
        _safe_update_task(task_id, {"status": "processing"})

        from app.services.agents.base import AgentContext
        from app.services.agents import get_registry
        registry = get_registry()

        # 进度回调：将 Agent 的实时步骤写入 task_store，供前端轮询
        def progress_callback(progress: dict):
            _safe_update_task(task_id, {
                "status": "processing",
                "progress": progress,
            })

        # 构建 Agent 上下文，注入进度回调
        context = AgentContext(
            session_id=session_id or str(uuid.uuid4()),
            user_message=message,
        )
        context._progress_callback = progress_callback

        # 确定目标 Agent
        if agent_role:
            target = registry.get(agent_role)
            if target is None:
                _safe_update_task(task_id, {"status": "failed", "error": f"Agent '{agent_role}' 不存在"})
                return
            result = await target.execute(context)
        else:
            router_agent = registry.get("intent_router")
            if router_agent is None:
                _safe_update_task(task_id, {"status": "failed", "error": "意图识别 Agent 未注册"})
                return
            result = await router_agent.execute(context)

        # 更新会话
        if session_id and session_id in _active_sessions:
            _active_sessions[session_id]['last_active'] = datetime.now().isoformat()
            _active_sessions[session_id]['question_count'] += 1

        # 转换 AgentResult 为任务结果
        _safe_update_task(task_id, {
            "status": "completed",
            "result": {
                "success": result.success,
                "answer": result.answer,
                "agent_role": result.agent_role,
                "agent_name": result.agent_name,
                "session_id": context.session_id,
                "processing_time": result.processing_time,
                "steps": [s.model_dump() for s in result.steps],
                "agent_chain": context.agent_chain,
                "meta": result.meta,
                "error": result.error,
            },
        })
    except Exception as e:
        logger.error(f"聊天任务 {task_id} 失败: {e}", exc_info=True)
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

@router.post("/initialize", response_model=SubmitTaskResponse, summary="初始化AI问答系统（后台执行）")
async def initialize_system(request: InitializeRequest):
    """提交初始化任务，后台执行，通过 /initialize-status/{task_id} 轮询进度"""
    task_id = str(uuid.uuid4())[:8]
    now_str = datetime.now().isoformat()

    _safe_create_task(task_id, {
        "task_id": task_id,
        "task_type": "initialize",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_str,
        "updated_at": now_str,
    })

    t = threading.Thread(target=_run_initialize_task, args=(task_id, request.force_rebuild), daemon=True)
    t.start()

    logger.info(f"初始化任务已提交: task_id={task_id}")
    return SubmitTaskResponse(task_id=task_id, status="pending", message="初始化任务已提交，请通过轮询接口查看进度")


@router.get("/initialize-status/{task_id}", response_model=TaskStatusResponse, summary="查询初始化任务状态")
async def get_initialize_status(task_id: str):
    """根据 task_id 查询系统初始化任务的执行状态和结果"""
    task = _safe_get_task(task_id)
    if not task or task.get("task_type") != "initialize":
        raise HTTPException(status_code=404, detail=f"初始化任务 {task_id} 不存在或已过期")

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        task_type=task.get("task_type", ""),
        result=task.get("result"),
        error=task.get("error"),
        created_at=task.get("created_at"),
        updated_at=task.get("updated_at"),
    )


@router.post("/ask", response_model=SubmitTaskResponse, summary="提问（后台执行，老系统兼容）")
async def ask_question(request: QuestionRequest):
    """提交问答任务（老系统兼容接口），推荐使用 /chat"""
    if _qa_system_instance is None or not _qa_system_instance.is_initialized:
        raise HTTPException(status_code=503, detail="QA系统未初始化，请先调用/initialize接口")

    task_id = str(uuid.uuid4())[:8]
    session_id = request.session_id or str(uuid.uuid4())
    now_str = datetime.now().isoformat()

    _safe_create_task(task_id, {
        "task_id": task_id,
        "task_type": "ask",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_str,
        "updated_at": now_str,
        "question": request.question,
        "session_id": session_id,
    })

    t = threading.Thread(target=_run_ask_task, args=(task_id, request.question, session_id), daemon=True)
    t.start()

    logger.info(f"问答任务已提交: task_id={task_id}")
    return SubmitTaskResponse(task_id=task_id, status="pending", message="问答任务已提交，请通过轮询接口查看结果")


@router.get("/ask-status/{task_id}", response_model=TaskStatusResponse, summary="查询问答任务状态")
async def get_ask_status(task_id: str):
    """根据 task_id 查询问答任务的执行状态和结果"""
    task = _safe_get_task(task_id)
    if not task or task.get("task_type") != "ask":
        raise HTTPException(status_code=404, detail=f"问答任务 {task_id} 不存在或已过期")

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
            "service": "AI智能问答API",
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


# ==================== 多 Agent 系统接口 ====================

def _get_agent_registry():
    """延迟导入 Agent 注册中心"""
    from app.services.agents import get_registry
    return get_registry()


@router.post("/chat", response_model=SubmitTaskResponse, summary="多 Agent 聊天（后台执行）")
async def chat(request: ChatRequest):
    """
    统一聊天入口。

    - 不指定 agent_role 时，自动通过意图识别 Agent 路由到合适的 Agent。
    - 指定 agent_role 时，直接调用目标 Agent。
    """
    task_id = str(uuid.uuid4())[:8]
    session_id = request.session_id or str(uuid.uuid4())
    now_str = datetime.now().isoformat()

    _safe_create_task(task_id, {
        "task_id": task_id,
        "task_type": "chat",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_str,
        "updated_at": now_str,
        "message": request.message,
        "session_id": session_id,
    })

    asyncio.create_task(_run_chat_task(task_id, request.message, session_id, request.agent_role))

    return SubmitTaskResponse(task_id=task_id, status="pending", message="聊天任务已提交")


@router.get("/chat-status/{task_id}", response_model=ChatStatusResponse, summary="查询聊天任务状态")
async def get_chat_status(task_id: str):
    """查询多 Agent 聊天任务的执行状态（含实时进度）"""
    task = _safe_get_task(task_id)
    if not task or task.get("task_type") != "chat":
        raise HTTPException(status_code=404, detail=f"聊天任务 {task_id} 不存在")

    response = ChatStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        task_type=task.get("task_type", "chat"),
        result=task.get("result"),
        error=task.get("error"),
        created_at=task.get("created_at"),
        updated_at=task.get("updated_at"),
    )
    # processing 状态时附加实时进度
    if task["status"] == "processing" and task.get("progress"):
        response.progress = task["progress"]
    return response


@router.get("/agents", summary="获取 Agent 列表")
async def list_agents():
    """获取所有已注册的 Agent 及其状态"""
    registry = _get_agent_registry()
    agents = []
    for info in registry.list_agents():
        agent = registry.get(info["role"])
        agents.append(AgentInfo(
            role=info["role"],
            name=info["name"],
            description=info["description"],
            initialized=agent.is_initialized if agent else False,
        ).model_dump())
    return {"agents": agents}


@router.get("/", summary="API根路径")
async def api_root():
    return {
        "name": "AI代码智能问答系统API",
        "version": "1.0.0",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/aiagent/chat", "description": "多 Agent 聊天（自动路由）"},
            {"method": "GET",  "path": "/api/v1/aiagent/chat-status/{task_id}", "description": "查询聊天任务状态"},
            {"method": "GET",  "path": "/api/v1/aiagent/agents", "description": "获取 Agent 列表"},
            {"method": "POST", "path": "/api/v1/aiagent/initialize", "description": "初始化 QA 系统"},
            {"method": "GET",  "path": "/api/v1/aiagent/initialize-status/{task_id}", "description": "查询初始化状态"},
            {"method": "POST", "path": "/api/v1/aiagent/ask", "description": "直接提问（旧接口）"},
            {"method": "GET",  "path": "/api/v1/aiagent/ask-status/{task_id}", "description": "查询问答状态"},
            {"method": "GET",  "path": "/api/v1/aiagent/health", "description": "健康检查"},
        ],
        "documentation": "/docs",
        "openapi_schema": "/openapi.json",
    }
