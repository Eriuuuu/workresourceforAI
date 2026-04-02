from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query, Body,File,UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid
import json
import asyncio
from datetime import datetime
from loguru import logger

from app.services.ai_code_qa_system.main_system import LangChainCodeQASystem,GlodonTestcasesGenerater
from app.core.config_for_ai_service import get_settings, get_config_manager
from app.models.ai_system_model import *

from app.services.ai_testcasegen_system.TCGen_requirement_parser import RequirementParser
from app.services.ai_testcasegen_system.TCGen_base_glodon_llm import GlodonBaseLLM
from app.services.ai_code_qa_system.glodon_api_token import get_glodon_token
from app.services.ai_testcasegen_system.TCGen_requirement_graph_manager import RequirementGraphManager
from app.services.ai_testcasegen_system.TCGen_main import RequirementKnowledgeGraph, IntegrateGlodonTestcasegenWorkflow,readdocxfile



# 创建路由
router = APIRouter()
# 全局变量存储QA系统实例
_qa_system_instance = None
_active_sessions = {}  # 多会话支持


# ==================== 依赖注入和工具函数 ====================
def get_config():
    """获取配置"""
    return get_config_manager()

def get_qa_system() -> LangChainCodeQASystem:
    """获取QA系统实例"""
    global _qa_system_instance
    if _qa_system_instance is None:
        raise HTTPException(
            status_code=503,
            detail="QA系统未初始化，请先调用/initialize接口"
        )
    return _qa_system_instance

def get_session(session_id: str) -> Dict[str, Any]:
    """获取会话"""
    if session_id not in _active_sessions:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return _active_sessions[session_id]

# async def initialize_background():
#     """后台初始化系统"""
#     global _qa_system_instance
#     try:
#         logger.info("开始后台初始化QA系统...")
#         config = get_config()
        
#         # 创建系统实例
#         _qa_system_instance = LangChainCodeQASystem(config)
        
#         # 初始化系统
#         _qa_system_instance.initialize(force_rebuild=True)
        
#         logger.info("QA系统后台初始化完成")
#     except Exception as e:
#         logger.error(f"后台初始化失败: {e}")
#         _qa_system_instance = None


# ==================== API路由 ====================
@router.post("/initialize", response_model=InitializeResponse, summary="初始化AI问答系统", description="初始化代码问答系统，包括加载代码库、构建索引等")
async def initialize_system(
    request: InitializeRequest = Body(...),
    background_tasks: BackgroundTasks = None
):
    """初始化系统"""
    global _qa_system_instance
    
    try:
        logger.info(f"开始初始化AI问答系统，force_rebuild={request.force_rebuild}")
        
        # 获取配置
        config = get_config()
        
        # 如果指定了代码库路径，更新配置
        if request.codebase_path:
            logger.info(f"使用指定代码库路径: {request.codebase_path}")
            # 这里需要根据您的配置结构来设置
            # config.system.codebase_path = request.codebase_path
        
        # 创建系统实例
        _qa_system_instance = LangChainCodeQASystem(config)
        
        # 初始化系统
        _qa_system_instance.initialize(force_rebuild=request.force_rebuild)
        
        # 生成系统ID
        system_id = str(uuid.uuid4())
        
        # 获取系统统计信息
        system_stats = _qa_system_instance.get_system_status()
        
        logger.info(f"AI问答系统初始化成功，系统ID: {system_id}")
        
        return InitializeResponse(
            success=True,
            message="AI问答系统初始化成功",
            system_id=system_id,
            initialization_time=datetime.now().isoformat(),
            stats=system_stats
        )
        
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"系统初始化失败: {str(e)}"
        )

@router.post("/ask", response_model=QuestionResponse, summary="提问", description="向AI系统提问关于代码的问题")
async def ask_question(
    request: QuestionRequest,
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """提问接口"""
    try:
        # 获取或创建会话
        session_id = request.session_id
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # 记录会话活动
        if session_id not in _active_sessions:
            _active_sessions[session_id] = {
                'created_at': datetime.now().isoformat(),
                'question_count': 0,
                'last_active': datetime.now().isoformat()
            }
        
        session = _active_sessions[session_id]
        session['last_active'] = datetime.now().isoformat()
        
        logger.info(f"处理问题，会话ID: {session_id}, 问题: {request.question[:100]}...")
        
        # 流式响应处理（简化版，实际需要SSE或WebSocket）
        if request.stream:
            # 这里简化为普通响应，实际流式响应需要特殊处理
            logger.warning("流式响应暂未完全实现，使用普通响应")
        
        # 调用QA系统提问
        result = qa_system.ask_question(request.question)
        
        # 更新会话统计
        session['question_count'] += 1
        
        # 构建响应
        response = QuestionResponse(
            success=result.get('success', False),
            answer=result.get('answer'),
            question=request.question,
            session_id=session_id,
            source_files=result.get('source_files', []),
            files_count=result.get('files_count', 0),
            token_usage=result.get('token_usage'),
            processing_time=result.get('processing_time', 0),
            error=result.get('error')
        )
        
        if response.success:
            logger.info(f"问题处理成功，会话: {session_id}, 耗时: {response.processing_time:.2f}秒")
        else:
            logger.error(f"问题处理失败: {response.error}")
        
        return response
        
    except Exception as e:
        logger.error(f"提问接口出错: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"处理问题失败: {str(e)}"
        )

################################# 用例生成助手  #########

@router.post("/getdocx",  summary="获取文档", description="获取上传的需求文档并解析文本内容")
async def get_docx(file: UploadFile =File(...)):
    res = await readdocxfile(file)
    if res:
        return {
            "code": 200,
            "message": "Load file successfully",
            "data": res
      }
    else:
        return {
            "code": 404,
            "message": "Load file failed",
            "data": ''
      }


_casegen_llm_instance = None

@router.post("/initialize3", summary="初始化AI问答系统", description="初始化代码问答系统，包括加载代码库、构建索引等")
async def initialize_system(requirement_str):
    """初始化系统"""
    global _casegen_llm_instance
    
    try:

        config = get_config()
        _casegen_llm_instance = GlodonBaseLLM(
            get_config(),
            get_glodon_token()
        )
        title="【25Q4】着色模式下对遮挡模型拾取捕捉的差异化处理"
        text=requirement_str
        print(requirement_str)
        print("111111111111")
        # doc_processor = RequirementKnowledgeGraph(_casegen_llm_instance,config.db.neo4j_uri,config.db.neo4j_username,config.db.neo4j_password)
        # # doc_process_result = doc_processor.process_requirement_document(title,text)
        # research_result = doc_processor.query_related_content("拾取","search")
        # print(research_result["results"])
        # print(type(research_result["results"]))
        # status = doc_processor.get_system_status()
        # print(status)
        # testcasesgen = IntegrateGlodonTestcasegenWorkflow(
        #     get_glodon_token(),
        #     research_result["results"]
        # )
        # entities_string = testcasesgen.process_entities()
        # testcasesgen.excute_test_gen(text,entities_string)
        return True
        
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"系统初始化失败: {str(e)}"
        )



#################################   以下暂不使用   ################

@router.get("/sessions/{session_id}",
           response_model=SessionInfo,
           summary="获取会话信息",
           description="获取指定会话的详细信息")
async def get_session_info(
    session_id: str,
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """获取会话信息"""
    try:
        session = get_session(session_id)
        
        # 获取系统状态
        system_status = qa_system.get_system_status()
        
        # 获取对话历史
        conversation_history = qa_system.get_conversation_history() if hasattr(qa_system, 'get_conversation_history') else []
        
        return SessionInfo(
            session_id=session_id,
            created_at=session['created_at'],
            last_active=session['last_active'],
            question_count=session['question_count'],
            conversation_history_count=len(conversation_history),
            system_status=system_status
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions",
           response_model=List[SessionInfo],
           summary="获取所有活跃会话",
           description="获取当前所有活跃的会话列表")
async def get_all_sessions(
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """获取所有活跃会话"""
    try:
        sessions_info = []
        
        for session_id, session_data in _active_sessions.items():
            # 获取对话历史（这里简化处理，实际可能需要为每个会话单独存储）
            conversation_history = []
            if qa_system.qa_system:
                conversation_history = qa_system.qa_system.get_conversation_history()
            
            sessions_info.append(SessionInfo(
                session_id=session_id,
                created_at=session_data['created_at'],
                last_active=session_data['last_active'],
                question_count=session_data['question_count'],
                conversation_history_count=len(conversation_history),
                system_status=qa_system.get_system_status()
            ))
        
        return sessions_info
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}",
              summary="删除会话",
              description="删除指定会话")
async def delete_session(session_id: str):
    """删除会话"""
    try:
        if session_id in _active_sessions:
            del _active_sessions[session_id]
            logger.info(f"已删除会话: {session_id}")
            return {"success": True, "message": f"会话 {session_id} 已删除"}
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status",
           response_model=SystemStatus,
           summary="系统状态检查",
           description="获取系统当前状态")
async def get_system_status(
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """获取系统状态"""
    try:
        system_status = qa_system.get_system_status()
        
        return SystemStatus(
            initialized=system_status.get('initialized', False),
            initialization_time=system_status.get('initialization_time'),
            codebase_info=system_status.get('codebase'),
            vector_database_stats=system_status.get('vector_database'),
            graph_database_stats=system_status.get('graph_database'),
            active_sessions=len(_active_sessions),
            system_stats=system_status.get('system_stats')
        )
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/debug/retrieval",
            response_model=DebugRetrievalResponse,
            summary="调试检索",
            description="调试检索系统，查看检索到的文件")
async def debug_retrieval(
    request: DebugRetrievalRequest,
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """调试检索"""
    try:
        import time
        start_time = time.time()
        
        # 调用调试检索
        debug_result = qa_system.debug_retrieval(request.question)
        
        # 提取文件信息
        retrieved_files = []
        if 'retrieved_documents' in debug_result:
            for doc in debug_result['retrieved_documents']:
                retrieved_files.append({
                    'file_path': doc.get('file_path', '未知'),
                    'similarity': doc.get('similarity', 0),
                    'content_preview': doc.get('content', '')[:200] + '...' if len(doc.get('content', '')) > 200 else doc.get('content', ''),
                    'metadata': doc.get('metadata', {})
                })
        
        processing_time = time.time() - start_time
        
        return DebugRetrievalResponse(
            question=request.question,
            retrieved_files=retrieved_files,
            count=len(retrieved_files),
            processing_time=processing_time
        )
    except Exception as e:
        logger.error(f"调试检索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear",
            summary="清空对话历史",
            description="清空当前对话历史")
async def clear_conversation_history(
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """清空对话历史"""
    try:
        qa_system.clear_conversation_history()
        return {"success": True, "message": "对话历史已清空"}
    except Exception as e:
        logger.error(f"清空对话历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rebuild-index",
            summary="重建索引",
            description="重新构建代码索引")
async def rebuild_index(
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """重建索引"""
    try:
        qa_system.rebuild_index()
        return {
            "success": True,
            "message": "索引重建完成",
            "time": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"重建索引失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health",
           summary="健康检查",
           description="检查API服务是否正常运行")
async def health_check():
    """健康检查"""
    try:
        # 检查系统是否初始化
        system_ok = _qa_system_instance is not None and _qa_system_instance.is_initialized
        
        health_data = {
            "status": "healthy" if system_ok else "unhealthy",
            "service": "AI智能代理API",
            "timestamp": datetime.now().isoformat(),
            "system_initialized": system_ok,
            "active_sessions": len(_active_sessions),
            "version": "1.0.0"
        }
        
        if system_ok:
            # 添加更多健康信息
            health_data.update({
                "codebase_path": _qa_system_instance.config.system.codebase_path,
                "initialization_time": _qa_system_instance.initialization_time.isoformat() if _qa_system_instance.initialization_time else None
            })
        
        return JSONResponse(content=health_data, status_code=200 if system_ok else 503)
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            status_code=503
        )

@router.get("/config",
           summary="获取配置",
           description="获取当前系统配置")
async def get_configuration(
    qa_system: LangChainCodeQASystem = Depends(get_qa_system)
):
    """获取配置"""
    try:
        config = qa_system.config
        
        return {
            "codebase_path": config.system.codebase_path,
            "chunk_size": config.system.chunk_size,
            "chunk_overlap": config.system.chunk_overlap,
            "max_files_per_query": config.system.max_files_per_query,
            "llm_model": config.api.glodonai_llm_model,
            "vector_store_path": config.db.chroma_persist_dir,
            "neo4j_uri": config.db.neo4j_uri
        }
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/",
           summary="API根路径",
           description="获取API基本信息")
async def api_root():
    """API根路径"""
    return {
        "name": "AI代码智能问答系统API",
        "version": "1.0.0",
        "description": "基于LangChain和Glodon AI的代码智能问答系统",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/aiagent/initialize", "description": "初始化系统"},
            {"method": "POST", "path": "/api/v1/aiagent/ask", "description": "提问"},
            {"method": "GET", "path": "/api/v1/aiagent/status", "description": "系统状态"},
            {"method": "GET", "path": "/api/v1/aiagent/health", "description": "健康检查"},
            {"method": "GET", "path": "/api/v1/aiagent/sessions", "description": "会话列表"},
            {"method": "GET", "path": "/api/v1/aiagent/sessions/{session_id}", "description": "会话详情"},
            {"method": "POST", "path": "/api/v1/aiagent/clear", "description": "清空对话历史"},
            {"method": "POST", "path": "/api/v1/aiagent/rebuild-index", "description": "重建索引"},
            {"method": "POST", "path": "/api/v1/aiagent/debug/retrieval", "description": "调试检索"}
        ],
        "documentation": "/docs",
        "openapi_schema": "/openapi.json"
    }