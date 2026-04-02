import sys
import json
from loguru import logger
from app.core.config import get_settings

settings = get_settings()

def setup_logging():

    """配置结构化日志系统
    
    功能：
    1. 移除默认处理器
    2. 配置控制台输出
    3. 配置文件输出
    4. 配置结构化JSON格式（生产环境）
    """
    logger.remove()
    # 控制台日志配置
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
        # enqueue=True,
        backtrace=True,  # 启用堆栈跟踪
        diagnose=True    # 显示变量值
    )
    # 文件日志配置 - 开发环境
    if settings.DEBUG:
        logger.add(
        "logs/backend/backend_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",
            retention="30 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}| {extra}"
        )
    # 文件日志配置 - 生产环境（JSON格式）
    else:
        def serialize(record):
            """序列化日志记录为JSON格式"""
            subset = {
                "timestamp": record["time"].isoformat(),
                "level": record["level"].name,
                "message": record["message"],
                "module": record["name"],
                "function": record["function"],
                "line": record["line"],
                "extra": record.get("extra", {})
            }
            return json.dumps(subset)
        
        logger.add(
            "logs/backend/backend_{time:YYYY-MM-DD}.json",
            level=settings.LOG_LEVEL,
            rotation="00:00",
            retention="30 days",
            compression="zip",
            serialize=serialize  # 使用JSON格式
        )
    
    logger.info("✅ Logging system initialized")

# 自动调用配置
setup_logging()