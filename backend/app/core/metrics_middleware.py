"""HTTP Metrics Middleware

基于 Starlette BaseHTTPMiddleware，为每个 HTTP 请求记录：
- 请求数 (http_requests_total)
- 请求耗时 (http_request_duration_seconds)
- 并发数 (http_requests_in_flight)

SSE 流式请求记录完整生命周期耗时（从进入到流结束）。
"""

import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.core.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    REQUESTS_IN_FLIGHT,
)

# Path 归一化：将动态参数替换为占位符
_PATH_PATTERNS = [
    (re.compile(r"/ingest/tasks/[^/]+"), "/ingest/tasks/{task_id}"),
    (re.compile(r"/questions/\d+"), "/questions/{question_id}"),
]


def _normalize_path(path: str) -> str:
    """将含动态参数的 URL path 归一化，控制 Prometheus label 基数。"""
    for pattern, replacement in _PATH_PATTERNS:
        path = pattern.sub(replacement, path)
    return path


def _is_sse(response: Response) -> bool:
    """判断响应是否为 SSE 流。"""
    ct = response.headers.get("content-type", "")
    return "text/event-stream" in ct


class MetricsMiddleware(BaseHTTPMiddleware):
    """记录 HTTP 请求指标的中间件。

    对普通请求：在 response 返回后立即记录指标。
    对 SSE 请求：包装 body_iterator，在流结束时记录指标。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 排除 /metrics 端点自身，避免递归
        if request.url.path == "/metrics":
            return await call_next(request)

        REQUESTS_IN_FLIGHT.inc()
        path = _normalize_path(request.url.path)
        method = request.method
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            REQUEST_COUNT.labels(method=method, path=path, status="500").inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(
                time.perf_counter() - start
            )
            REQUESTS_IN_FLIGHT.dec()
            raise

        status = str(response.status_code)

        if _is_sse(response):
            # SSE：包装 body iterator，在流结束时记录指标
            wrapped_body = _sse_body_wrapper(
                response.body_iterator, method, path, status, start
            )
            return StreamingResponse(
                content=wrapped_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # 普通请求：直接记录
        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(
            time.perf_counter() - start
        )
        REQUESTS_IN_FLIGHT.dec()
        return response


async def _sse_body_wrapper(
    body_iterator,
    method: str,
    path: str,
    status: str,
    start: float,
):
    """包装 SSE body iterator：passthrough 每个 chunk，在结束时记录指标。"""
    try:
        async for chunk in body_iterator:
            yield chunk
    finally:
        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(
            time.perf_counter() - start
        )
        REQUESTS_IN_FLIGHT.dec()
