from fastapi import APIRouter, Depends
from app.databases.mongodb import get_database
import psutil
import time

router = APIRouter()

@router.get("/health")
async def health_check():
    """基础健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "enterprise-api",
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(db=Depends(get_database)):
    """详细健康检查"""
    # 检查数据库连接
    db_status = "healthy"
    try:
        await db.command("ping")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # 系统指标
    system_info = {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("/").percent,
    }
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": time.time(),
        "database": db_status,
        "system": system_info
    }