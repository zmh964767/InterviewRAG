"""统计接口"""

import logging
from datetime import datetime

from fastapi import APIRouter

from app.models.schemas import StatsResponse
from app.models.database import Database

logger = logging.getLogger(__name__)
router = APIRouter()

# 模块级单例
_db: Database | None = None


def _get_db() -> Database:
    """获取数据库单例"""
    global _db
    if _db is None:
        _db = Database()
    return _db


@router.get("/stats", response_model=StatsResponse)
async def stats_endpoint():
    """知识库统计"""

    db = _get_db()
    questions = db.get_all_questions()

    categories: dict[str, int] = {}
    for q in questions:
        cat = q.get("category", "未分类")
        categories[cat] = categories.get(cat, 0) + 1

    return StatsResponse(
        total_questions=len(questions),
        categories=categories,
        last_updated=datetime.now().isoformat(),
    )
