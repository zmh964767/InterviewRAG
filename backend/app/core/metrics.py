"""Prometheus 指标定义

集中定义所有 Counter / Histogram / Gauge，供 middleware 和 service 层引用。
/metrics 端点也注册在此模块的 router 上。
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

router = APIRouter(tags=["metrics"])


# ─── HTTP 层 ──────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60],
)
REQUESTS_IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "Number of HTTP requests currently being processed",
)

# ─── RAG Pipeline ─────────────────────────────────────────────────────────

RAG_STAGE_LATENCY = Histogram(
    "rag_stage_duration_seconds",
    "RAG pipeline stage latency",
    ["stage"],  # cache_check, retrieval, rerank
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60],
)
CACHE_HITS = Counter("rag_cache_hits_total", "Semantic cache hits")
CACHE_MISSES = Counter("rag_cache_misses_total", "Semantic cache misses")

# ─── LLM 调用 ─────────────────────────────────────────────────────────────

LLM_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "LLM API call latency",
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60],
)
LLM_TOKENS = Histogram(
    "llm_tokens_used",
    "LLM tokens consumed per request",
    ["type"],  # prompt, completion
    buckets=[10, 50, 100, 250, 500, 1000, 2000, 4000],
)
LLM_ERRORS = Counter(
    "llm_errors_total",
    "LLM API call errors",
    ["error_type"],  # timeout, api_error, etc.
)

# ─── 系统级 ────────────────────────────────────────────────────────────────

ACTIVE_CONVERSATIONS = Gauge(
    "active_conversations",
    "Number of active conversations in memory",
)
RATE_LIMIT_REJECTIONS = Counter(
    "rate_limit_rejections_total",
    "Requests rejected by rate limiter",
)


# ─── RAG 阶段计时上下文管理器 ─────────────────────────────────────────────

@asynccontextmanager
async def track_stage(stage: str) -> AsyncGenerator[None, None]:
    """RAG Pipeline 阶段计时上下文管理器。

    用法::

        async with track_stage("retrieval"):
            sources = await self._retrieve(question)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        RAG_STAGE_LATENCY.labels(stage=stage).observe(time.perf_counter() - start)


# ─── /metrics 端点 ────────────────────────────────────────────────────────

@router.get("/metrics")
async def metrics():
    """Prometheus 抓取端点"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
