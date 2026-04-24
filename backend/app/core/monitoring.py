from prometheus_client import Counter, Histogram, generate_latest, REGISTRY, Gauge, CollectorRegistry
from fastapi import Response,Request
import time
from loguru import logger
from functools import wraps
from starlette.middleware.base import BaseHTTPMiddleware

# 定义Prometheus指标（使用 try/except 防止热加载时重复注册崩溃）
_PROMETHEUS_NAMES = [
    'http_requests_total',
    'http_request_duration_seconds',
    'database_operations_total',
    'database_operation_duration_seconds',
    'http_requests_active',
]

# 检测是否已有指标（热加载时模块被重新 import 但 REGISTRY 仍是同一个）
def _metric_exists(name: str) -> bool:
    for collector in REGISTRY._names_to_collectors.values():
        if hasattr(collector, '_name') and collector._name == name:
            return True
    return False

if _metric_exists('http_requests_total'):
    # 热加载：复用已有指标，避免 ValueError: Duplicated timeseries
    REQUEST_COUNT = REGISTRY._names_to_collectors.get('http_requests_total')
    REQUEST_DURATION = REGISTRY._names_to_collectors.get('http_request_duration_seconds')
    DB_OPERATION_COUNT = REGISTRY._names_to_collectors.get('database_operations_total')
    DB_OPERATION_DURATION = REGISTRY._names_to_collectors.get('database_operation_duration_seconds')
    ACTIVE_REQUESTS = REGISTRY._names_to_collectors.get('http_requests_active')
else:
    # 首次加载：创建指标
    REQUEST_COUNT = Counter(
        'http_requests_total',
        'Total HTTP Requests',
        ['method', 'endpoint', 'status_code']
    )
    REQUEST_DURATION = Histogram(
        'http_request_duration_seconds',
        'HTTP Request Duration',
        ['method', 'endpoint'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    )
    DB_OPERATION_COUNT = Counter(
        'database_operations_total',
        'Total Database Operations',
        ['operation', 'collection', 'status']
    )
    DB_OPERATION_DURATION = Histogram(
        'database_operation_duration_seconds',
        'Database Operation Duration',
        ['operation', 'collection'],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
    )
    ACTIVE_REQUESTS = Gauge(
        'http_requests_active',
        'Active HTTP Requests'
    )


async def metrics_endpoint(request:Request):
    """Prometheus指标端点"""
    return Response(generate_latest(REGISTRY), media_type="text/plain")

class MonitorMiddleware(BaseHTTPMiddleware):
    """监控中间件"""

    def __init__(self, app, exclude_paths=None):
        super().__init__(app)  # 调用父类初始化
        self.exclude_paths = exclude_paths or ['/metrics', '/health', '/docs']

    async def dispatch(self, request:Request, call_next):

        # 检查是否排除当前路径
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        start_time = time.time()
        ACTIVE_REQUESTS.inc()  # 增加活跃请求数

        try:

            response= await call_next(request)
            duration = time.time() - start_time

            # 记录指标
            REQUEST_COUNT.labels(
                method = request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)

            # 记录慢请求
            if duration > 1.0:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {duration:.2f}s"
                )
            
            return response

        except Exception as e:
            # 记录错误请求
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=500
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            logger.error(f"Request failed: {request.method} {request.url.path} - {e}")
            raise
            
        finally:
            ACTIVE_REQUESTS.dec()  # 减少活跃请求数

    # 数据库监控装饰器
def monitor_db_operation(operation: str, collection: str):
    """监控数据库操作的装饰器"""
    def decorator(func):
        @wraps(func)                 #作用：保留原始函数的元信息（名称、文档字符串等）
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                # 执行原始函数
                result = await func(*args, **kwargs)
                
                # 记录成功指标
                DB_OPERATION_COUNT.labels(
                    operation=operation,
                    collection=collection,
                    status='success'
                ).inc()
                
                duration = time.time() - start_time
                
                # 记录耗时指标
                DB_OPERATION_DURATION.labels(
                    operation=operation,
                    collection=collection
                ).observe(duration)
                
                # 记录慢查询
                if duration > 0.1:  # 超过100ms的查询
                    logger.warning(
                        f"Slow DB operation: {operation} on {collection} "
                        f"took {duration:.3f}s"
                    )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # 记录失败指标
                DB_OPERATION_COUNT.labels(
                    operation=operation,
                    collection=collection,
                    status='error'
                ).inc()
                
                # 记录耗时指标（包括失败的操作）
                DB_OPERATION_DURATION.labels(
                    operation=operation,
                    collection=collection
                ).observe(duration)
                
                logger.error(
                    f"DB operation failed: {operation} on {collection} - {e}"
                )
                raise
        return wrapper
    return decorator