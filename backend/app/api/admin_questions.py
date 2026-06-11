"""管理端：题目管理 API（受 JWT 保护）

GET    /api/admin/questions       — 分页查询（管理端完整功能）
DELETE /api/admin/questions/{id}  — 删除单条
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db, get_rag_service
from app.api.deps_admin import require_admin
from app.core.exceptions import NotFoundError
from app.models.database import Database
from app.models.schemas import (
    DeleteQuestionResponse,
    QuestionListResponse,
)
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/questions", response_model=QuestionListResponse)
async def list_questions(
    page: int = Query(1, ge=1, description="1-based 页码"),
    size: int = Query(20, ge=1, le=100, description="页大小（max 100）"),
    q: str = Query("", description="搜索关键词（题面+答案）"),
    category: str = Query("", description="分类精确匹配"),
    difficulty: str = Query("", description="难度精确匹配"),
    db: Database = Depends(get_db),
):
    """分页查询题目（管理端）"""
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


@router.delete("/questions/{question_id}", response_model=DeleteQuestionResponse)
async def delete_question(
    question_id: str,
    db: Database = Depends(get_db),
    rag: RAGService = Depends(get_rag_service),
):
    """删除单条题目"""
    try:
        rag.vector_store.delete_by_id(question_id)
    except Exception as e:
        logger.error(f"ChromaDB 删除失败: {e}")
        raise HTTPException(status_code=500, detail=f"ChromaDB 删除失败: {e}")

    if not db.delete_by_id(question_id):
        raise NotFoundError("题目", question_id)

    return DeleteQuestionResponse(deleted=True, id=question_id)
