"""管理端 API 路由汇总

将 admin_* 模块的路由统一集中到一个 router，方便 main.py 注册。
"""

import logging

from fastapi import APIRouter, Depends

from app.api import admin_ingest, admin_stats, admin_eval, admin_questions
from app.api import admin_change_password
from app.api import deps as deps_mod
from app.api import feedback
from app.api.deps_admin import require_admin
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

router.include_router(admin_ingest.router)
router.include_router(admin_stats.router)
router.include_router(admin_eval.router)
router.include_router(admin_questions.router)
router.include_router(admin_change_password.router)
# 反馈管理端(GET /feedback, /feedback/stats) — feedback.router 自身已带 require_admin on these endpoints
router.include_router(feedback.router)


@router.get("/cache/stats", dependencies=[Depends(require_admin)])
async def cache_stats(rag: RAGService = Depends(deps_mod.get_rag_service)) -> dict:
    """缓存统计（条目数、命中次数、过期数）"""
    if not rag.cache:
        return {"enabled": False, "total": 0, "expired": 0, "hit_count_total": 0}
    stats = rag.cache.stats()
    return {"enabled": True, **stats}


@router.post("/cache/flush", dependencies=[Depends(require_admin)])
async def cache_flush(rag: RAGService = Depends(deps_mod.get_rag_service)) -> dict:
    """手动清空缓存"""
    if not rag.cache:
        return {"flushed": 0, "message": "缓存未启用"}
    deleted = rag.cache.invalidate()
    return {"flushed": deleted}
