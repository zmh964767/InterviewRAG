"""管理端：统计接口

GET /api/admin/stats — 知识库统计
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.api.deps_admin import require_admin
from app.models.database import Database
from app.models.schemas import StatsResponse

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=StatsResponse)
async def stats_endpoint(db: Database = Depends(get_db)):
    """知识库统计"""
    total = db.count()
    categories = db.count_by_category()
    return StatsResponse(
        total_questions=total,
        categories=categories,
        last_updated=datetime.now().isoformat(),
    )
