"""健康检查接口"""

import logging

from fastapi import APIRouter, Depends

from app.api.deps import get_rag_service
from app.models.schemas import HealthResponse
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_endpoint(rag: RAGService = Depends(get_rag_service)):
    """健康检查（复用 lifespan 里的共享实例）"""

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

    return HealthResponse(
        status="ok",
        vector_count=vector_count,
        llm_status=llm_status,
    )
