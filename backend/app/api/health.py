"""健康检查接口"""

import logging
import time

from fastapi import APIRouter, Depends

from app.api.deps import get_rag_service
from app.models.schemas import HealthResponse
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter()

# Health check TTL 缓存（避免每次请求都调 LLM API）
_CACHE_TTL = 60  # seconds
_cache: dict | None = None
_cache_ts: float = 0


@router.get("/health", response_model=HealthResponse)
async def health_endpoint(rag: RAGService = Depends(get_rag_service)):
    """健康检查（复用 lifespan 里的共享实例）"""
    global _cache, _cache_ts

    now = time.monotonic()
    if _cache is not None and now - _cache_ts < _CACHE_TTL:
        return HealthResponse(**_cache)

    # 检查 VectorStore
    vector_count = 0
    try:
        vector_count = rag.vector_store.count()
    except Exception as e:
        logger.warning(f"VectorStore 查询异常: {e}")

    # 检查 LLM
    llm_status = "error"
    try:
        llm_status = rag.llm_service.check_health()
    except Exception as e:
        logger.warning(f"LLM 健康检查异常: {e}")

    status = "ok" if llm_status != "error" else "degraded"
    result = {
        "status": status,
        "vector_count": vector_count,
        "llm_status": llm_status,
    }
    _cache = result
    _cache_ts = time.monotonic()

    return HealthResponse(**result)


@router.get("/ping")
async def ping():
    """轻量存活检查（不调 LLM，给 docker healthcheck 用）"""
    return {"status": "ok"}
