"""知识库导入接口"""

import logging

from fastapi import APIRouter, UploadFile, File

from app.models.schemas import IngestRequest, IngestResponse
from app.services.ingest_service import IngestService

logger = logging.getLogger(__name__)
router = APIRouter()

# 模块级单例
_ingest_service: IngestService | None = None


def _get_ingest_service() -> IngestService:
    """获取导入服务单例"""
    global _ingest_service
    if _ingest_service is None:
        _ingest_service = IngestService()
    return _ingest_service


@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(request: IngestRequest):
    """从文件或 URL 导入面试题"""

    ingest_service = _get_ingest_service()

    if request.source_type == "md":
        result = await ingest_service.ingest_md(request.source)
    elif request.source_type == "pdf":
        result = await ingest_service.ingest_pdf(request.source)
    elif request.source_type == "url":
        result = await ingest_service.ingest_url(request.source)
    else:
        return IngestResponse(ingested=0, duplicates=0, errors=1)

    return IngestResponse(**result)


@router.post("/ingest/upload", response_model=IngestResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传文件导入"""

    ingest_service = _get_ingest_service()

    content = await file.read()
    filename = file.filename or "unknown"

    if filename.endswith(".md"):
        result = await ingest_service.ingest_md_content(content.decode("utf-8"), filename)
    elif filename.endswith(".pdf"):
        result = await ingest_service.ingest_pdf_content(content, filename)
    else:
        return IngestResponse(ingested=0, duplicates=0, errors=1)

    return IngestResponse(**result)
