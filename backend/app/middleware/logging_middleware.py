import time
from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件
    
    功能：
    1. 记录每个请求的详细信息
    2. 计算请求处理时间
    3. 记录响应状态
    4. 异常处理
    """

    async def dispatch(self, request: Request,call_next):
        start_time = time.time()

        logger.info(
            "Request started",
            extra ={
                "method":request.method,
                "url": str(request.url),
                "client_ip": request.client.host,
                "user_agent":request.headers.get("user-agent")
            }
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            logger.info(
                "Request completed",
                extra ={
                    "method":request.method,
                    "url":str(request.url),
                    "status_code": response.status_code,
                    "process_time":round(process_time, 4)
                }
            )
            # 添加处理时间到响应头
            response.headers["X-Process-Time"] = str(round(process_time, 4))
            
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.info(
                "Request failed",
                extra ={
                    "method":request.method,
                    "url":str(request.url),
                    "error": str(e),
                    "process_time":round(process_time, 4)
                }
            )
            raise