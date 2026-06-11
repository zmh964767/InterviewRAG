"""题目只读 API（公开，无鉴权）

GET /api/questions — 分页查询（支持 4 维过滤）
"""

import logging

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.models.database import Database
from app.models.schemas import QuestionListResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/questions", response_model=QuestionListResponse)
async def list_questions(
    page: int = Query(1, ge=1, description="1-based 页码"),
    size: int = Query(20, ge=1, le=100, description="页大小（max 100）"),
    q: str = Query("", description="搜索关键词（题面+答案）"),
    category: str = Query("", description="分类精确匹配"),
    difficulty: str = Query("", description="难度精确匹配"),
    db: Database = Depends(get_db),
):
    """分页查询题目，支持关键词+分类+难度三维过滤"""
    filters = {"q": q, "category": category, "difficulty": difficulty}
    items, total = db.list_questions(filters, page, size)
    categories = db.list_categories()
    return QuestionListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        categories=categories,
    )
