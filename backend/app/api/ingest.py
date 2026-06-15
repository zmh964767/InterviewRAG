"""知识库导入接口（异步版）

POST /api/ingest/upload        — Multipart 文件上传（异步，返回 task_id）
POST /api/ingest               — JSON 路径/URL 导入（异步，返回 task_id）
POST /api/ingest/insert-one    — 单条插入（同步，撤销机制用）
GET  /api/ingest/tasks         — 列出所有未完成任务
GET  /api/ingest/tasks/{id}    — 查询任务状态
"""

import asyncio
import hashlib
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_rag_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.schemas import (
    IngestTaskAccepted,
    InsertOneRequest,
    Question,
    TaskListResponse,
    TaskStatusResponse,
)
from app.services.ingest_service import IngestService
from app.services.rag_service import RAGService
from app.services.task_store import store as task_store

logger = logging.getLogger(__name__)
router = APIRouter()

# IngestService 单例（首次请求时用 RAGService 的 VectorStore 初始化）
_ingest_service: IngestService | None = None


def _get_ingest_service(rag: RAGService) -> IngestService:
    global _ingest_service
    if _ingest_service is None:
        _ingest_service = IngestService(vector_store=rag.vector_store)
    return _ingest_service


def _task_to_response(task) -> TaskStatusResponse:
    return TaskStatusResponse(**task.to_dict())


def _finalize_task(task_id: str, result: dict) -> None:
    """根据 ingest 返回的 dict 更新 task 终态"""
    ingested = result.get("ingested", 0)
    duplicates = result.get("duplicates", 0)
    errors = result.get("errors", 0)
    total = ingested + duplicates + errors
    task_store.update(
        task_id,
        status="done",
        ingested=ingested,
        duplicates=duplicates,
        errors=errors,
        total=total,
        done=total,
        finished_at=datetime.now().isoformat(),
    )


async def _run_task(task_id: str, coro, on_success=None) -> None:
    """通用后台任务包装器：执行 + 错误捕获 + 终态写入"""
    task_store.update(task_id, status="running")
    try:
        result = await coro
        _finalize_task(task_id, result)
        if on_success:
            on_success()
    except Exception as e:
        logger.error(f"任务 {task_id} 失败: {e}", exc_info=True)
        task_store.update(
            task_id,
            status="failed",
            error_message=str(e),
            finished_at=datetime.now().isoformat(),
        )


# =========================================================================
# 路由
# =========================================================================


@router.post(
    "/ingest",
    response_model=IngestTaskAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_endpoint(request: dict, rag: RAGService = Depends(get_rag_service)):
    """从服务端文件路径或 URL 异步导入

    Body: {"source": "data/questions.md", "source_type": "md|pdf|url"}
    """
    source = request.get("source", "").strip()
    source_type = request.get("source_type", "").strip()

    if not source or not source_type:
        raise ValidationError("source 和 source_type 必填")

    if source_type not in ("md", "pdf", "url"):
        raise ValidationError(f"不支持的 source_type: {source_type}")

    service = _get_ingest_service(rag)
    task = task_store.create(source_type, source)
    invalidate = rag.hybrid_retriever.invalidate

    if source_type == "md":
        asyncio.create_task(_run_task(task.task_id, service.ingest_md(source), on_success=invalidate))
    elif source_type == "pdf":
        asyncio.create_task(_run_task(task.task_id, service.ingest_pdf(source), on_success=invalidate))
    elif source_type == "url":
        asyncio.create_task(_run_task(task.task_id, service.ingest_url(source), on_success=invalidate))

    return IngestTaskAccepted(task_id=task.task_id)


@router.post(
    "/ingest/upload",
    response_model=IngestTaskAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_file(file: UploadFile = File(...), rag: RAGService = Depends(get_rag_service)):
    """上传文件异步导入"""
    filename = file.filename or "unknown"
    content = await file.read()

    # 文件大小限制: 10MB
    max_size = 10 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大: {len(content)} 字节，最大允许 {max_size} 字节 (10MB)",
        )

    if not (filename.endswith(".md") or filename.endswith(".pdf")):
        raise ValidationError(f"仅支持 .md / .pdf 文件: {filename}")

    service = _get_ingest_service(rag)
    task = task_store.create("upload", filename)

    if filename.endswith(".md"):
        coro = service.ingest_md_content(content.decode("utf-8"), filename)
    else:
        coro = service.ingest_pdf_content(content, filename)

    asyncio.create_task(_run_task(task.task_id, coro, on_success=rag.hybrid_retriever.invalidate))
    return IngestTaskAccepted(task_id=task.task_id)


@router.post("/ingest/insert-one", response_model=Question, status_code=201)
async def insert_one(request: InsertOneRequest, rag: RAGService = Depends(get_rag_service)):
    """单条插入（撤销机制用）

    id 由后端基于 md5(question|answer)[:16] 生成
    content_hash 冲突 → 409
    """
    # 稳定 id：md5(question|answer) 前 16 字符
    content_hash = hashlib.md5(
        f"{request.question}|{request.answer}".encode()
    ).hexdigest()[:16]

    service = _get_ingest_service(rag)

    # 构造 Question 对象
    q = Question(
        id=content_hash,
        question=request.question,
        answer=request.answer,
        category=request.category,
        difficulty=request.difficulty,
        source=request.source,
        tags=[],
    )

    # 1. 写入 SQLite
    inserted = service.db.insert_question(q.model_dump(mode="json"))
    if not inserted:
        # content_hash 冲突（重复题目）
        raise HTTPException(
            status_code=409,
            detail="题目已存在（content_hash 冲突）",
        )

    # 2. 写入 ChromaDB（向量）
    doc_text = f"题目：{request.question}\n\n答案：{request.answer}"
    try:
        service.vector_store.add_documents(
            ids=[content_hash],
            documents=[doc_text],
            metadatas=[{
                "question_id": content_hash,
                "category": request.category,
                "difficulty": request.difficulty,
                "source": request.source,
            }],
        )
        rag.hybrid_retriever.invalidate()
    except Exception as e:
        logger.error(f"insert-one ChromaDB 写入失败（SQLite 已成功）: {e}")

    return q


@router.get("/ingest/tasks", response_model=TaskListResponse)
async def list_tasks():
    """列出所有未完成任务"""
    tasks = task_store.list_active()
    return TaskListResponse(tasks=[_task_to_response(t) for t in tasks])


@router.get("/ingest/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str):
    """查询任务状态"""
    task = task_store.get(task_id)
    if task is None:
        raise NotFoundError("任务", task_id)
    return _task_to_response(task)
