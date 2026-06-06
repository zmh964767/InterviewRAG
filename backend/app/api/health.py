"""健康检查接口"""

import logging

from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.core.vectorstore import VectorStore
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()

# 模块级单例
_vector_store: VectorStore | None = None
_llm_service: LLMService | None = None


def _get_vector_store() -> VectorStore | None:
    """获取 VectorStore 单例，失败返回 None"""
    global _vector_store
    if _vector_store is None:
        try:
            _vector_store = VectorStore()
        except Exception as e:
            logger.warning(f"VectorStore 初始化失败: {e}")
            return None
    return _vector_store


def _get_llm_service() -> LLMService | None:
    """获取 LLM 服务单例，失败返回 None"""
    global _llm_service
    if _llm_service is None:
        try:
            _llm_service = LLMService()
        except Exception as e:
            logger.warning(f"LLM 服务初始化失败: {e}")
            return None
    return _llm_service


@router.get("/health", response_model=HealthResponse)
async def health_endpoint():
    """健康检查"""

    # 检查 VectorStore
    vs = _get_vector_store()
    vector_count = 0
    if vs is not None:
        try:
            vector_count = vs.count()
        except Exception as e:
            logger.warning(f"VectorStore 查询异常: {e}")

    # 检查 LLM
    llm_status = "error"
    llm = _get_llm_service()
    if llm is not None:
        try:
            llm_status = llm.check_health()
        except Exception as e:
            logger.warning(f"LLM 健康检查异常: {e}")
            llm_status = "error"

    return HealthResponse(
        status="ok",
        vector_count=vector_count,
        llm_status=llm_status,
    )
