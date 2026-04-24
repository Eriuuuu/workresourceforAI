from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from loguru import logger

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.logging_middleware import LoggingMiddleware
from app.core.monitoring import metrics_endpoint,MonitorMiddleware
from app.databases.mongodb import connect_to_mongo, close_mongo_connection
from app.api.v1.endpoints import auth, user, health, aiagent_api, testcasegen_api


setup_logging()
# 限流器
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期事件处理器"""
    # Startup: 应用启动时执行
    logger.info("🚀 Application starting up...")

    # 清理所有未完成的异步任务（服务重启后内存任务存储已清空，这里显式确认）
    from app.api.v1.endpoints.aiagent_api import _task_store, _task_store_lock
    with _task_store_lock:
        cleared_count = len(_task_store)
        _task_store.clear()
    if cleared_count > 0:
        logger.warning(f"后端重启，已清理 {cleared_count} 个未完成的异步任务")
    else:
        logger.info("异步任务存储已初始化（无残留任务）")

    await connect_to_mongo()

    # 注册多 Agent 系统
    from app.services.agents import setup_agents
    setup_agents()
    logger.info("多 Agent 系统已注册")

    # 应用运行中...
    yield

    # Shutdown: 应用关闭时执行
    logger.info("🛑 Application shutting down...")
    await close_mongo_connection()


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        description="企业级FastAPI应用",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan
    )
    # 中间件配置,中间件的配置顺序和执行顺序相反
    application.add_middleware(MonitorMiddleware)
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 限流异常处理
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler)

    # 包含路由
    application.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
    application.include_router(user.router, prefix="/api/v1/user", tags=["user"])
    application.include_router(health.router, prefix="/api/v1", tags=["health"])
    application.include_router(aiagent_api.router, prefix="/api/v1/aiagent", tags=["aiagent"])
    application.include_router(testcasegen_api.router, prefix="/api/v1/testcase", tags=["testcase"])
    
    # 监控端点
    if settings.ENABLE_METRICS:
        application.add_route("/metrics", metrics_endpoint)

    return application

app = create_application()

@app.get("/", tags=["Root"])
@limiter.limit("60/minute")
async def read_root(request: Request):
    return {"message": "欢迎来到GCMP QA Web开发示例程序",
            "status":"running",
            "docs":"/docs",
            "health":"/api/v1/health"
            }