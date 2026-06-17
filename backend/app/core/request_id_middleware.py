"""Request ID 中间件

为每个请求生成或读取 X-Request-ID，绑定到 structlog contextvars。
整个请求链路的日志自动携带 request_id。
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Request ID 中间件。

    - 优先读取客户端传入的 X-Request-ID 请求头
    - 未提供时自动生成 uuid4
    - 绑定到 structlog contextvars（自动注入每条日志）
    - 响应头返回 X-Request-ID
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # 绑定到 structlog contextvars
        # 注意：Python 3.11 的 run_in_executor 不自动复制 contextvars 到子线程
        # 事件循环中的日志（query 入口、retrieval、rerank）有 request_id
        # 线程池中的日志（cache check、LLM 调用）可能缺少 request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            structlog.contextvars.clear_contextvars()
