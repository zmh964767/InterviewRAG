"""用户反馈 API

- 公开端: POST /api/feedback
- 管理端: GET  /api/admin/feedback
- 管理端: GET  /api/admin/feedback/stats
- 管理端: GET  /api/admin/feedback/export

注: 此 router 内部路径不带 /api 前缀,挂载时再分别加 /api(公开) 和 /api/admin(管理)。
公开端 vs 管理端 在路由层面共处一文件但 auth 不同:
- POST /feedback 无 auth
- GET /feedback, /feedback/stats, /feedback/export 显式 Depends(require_admin)
"""

import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps_admin import require_admin
from app.core.db import get_db
from app.models.schemas import SubmitFeedbackRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/feedback", status_code=201)
async def submit_feedback(request: Request, body: SubmitFeedbackRequest) -> dict:
    """公开端:用户提交反馈(同一 message_id 自动覆盖)"""
    db = get_db()
    feedback_id = db.insert_feedback(
        {
            "message_id": body.message_id,
            "conversation_id": body.conversation_id,
            "rating": body.rating,
            "comment": body.comment,
            "message_content": body.message_content,
            "message_role": body.message_role,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", ""),
        }
    )
    return {"id": feedback_id, "message_id": body.message_id}


@router.get("/feedback", dependencies=[Depends(require_admin)])
async def admin_get_feedback(
    rating: int | None = Query(None, description="筛选: 1=👍 / -1=👎"),
    since: str | None = Query(None, description="起始时间 (ISO 字符串)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> dict:
    """管理端:反馈列表(分页 + 筛选)"""
    db = get_db()
    return db.get_feedback(rating=rating, since=since, page=page, size=size)


@router.get("/feedback/stats", dependencies=[Depends(require_admin)])
async def admin_get_feedback_stats(
    since: str | None = Query(None, description="起始时间 (ISO 字符串)"),
) -> dict:
    """管理端:反馈统计(👍 / 👎 / 差评率)"""
    db = get_db()
    return db.get_feedback_stats(since=since)


@router.get("/feedback/export", dependencies=[Depends(require_admin)])
async def admin_export_feedback(
    rating: int | None = Query(None, description="筛选: 1=👍 / -1=👎"),
    since: str | None = Query(None, description="起始时间 (ISO 字符串)"),
) -> StreamingResponse:
    """管理端:导出 CSV(UTF-8 BOM 让 Excel 正确识别中文)"""
    db = get_db()
    # size=10000 限制单次导出上限,够试用阶段;未来可加分页
    result = db.get_feedback(rating=rating, since=since, page=1, size=10000)
    items = result["items"]

    output = io.StringIO()
    # UTF-8 BOM:'﻿' 让 Excel 自动识别 UTF-8,中文不乱码
    output.write("﻿")
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)  # 所有字段加双引号
    writer.writerow(
        [
            "created_at",
            "rating",
            "comment",
            "message_id",
            "conversation_id",
            "message_content",
            "message_role",
            "client_ip",
            "user_agent",
        ]
    )
    for fb in items:
        writer.writerow(
            [
                fb.get("created_at", ""),
                fb.get("rating", ""),
                fb.get("comment", "") or "",
                fb.get("message_id", ""),
                fb.get("conversation_id", ""),
                fb.get("message_content", ""),
                fb.get("message_role", ""),
                fb.get("client_ip", "") or "",
                fb.get("user_agent", "") or "",
            ]
        )

    csv_content = output.getvalue()
    filename = f"feedback_{datetime.now().strftime('%Y-%m-%d')}.csv"
    # 注意:filename 不加引号 — FastAPI 会自己 escape,加了反而可能多出尾部引号
    return StreamingResponse(
        iter([csv_content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
