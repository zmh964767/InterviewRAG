"""题目管理 API

GET    /api/questions       — 分页查询（支持 4 维过滤）
DELETE /api/questions/{id}  — 删除单条（先 ChromaDB 再 SQLite，安全失败方向）
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db, get_rag_service
from app.core.exceptions import NotFoundError
from app.models.database import Database
from app.models.schemas import (
    DeleteQuestionResponse,
    QuestionListResponse,
)
from app.services.rag_service import RAGService

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


@router.delete("/questions/{question_id}", response_model=DeleteQuestionResponse)
async def delete_question(
    question_id: str,
    db: Database = Depends(get_db),
    rag: RAGService = Depends(get_rag_service),
):
    """删除单条题目

    顺序（安全失败方向）：
    1. ChromaDB：失败 → 500，两边都还在
    2. SQLite：失败 → 500，列表少一条但聊天搜不到（最坏失败方向）
    """
    # 1. 先 ChromaDB
    try:
        rag.vector_store.delete_by_id(question_id)
    except Exception as e:
        logger.error(f"ChromaDB 删除失败: {e}")
        raise HTTPException(status_code=500, detail=f"ChromaDB 删除失败: {e}")

    # 2. 再 SQLite
    if not db.delete_by_id(question_id):
        raise NotFoundError("题目", question_id)

    return DeleteQuestionResponse(deleted=True, id=question_id)
