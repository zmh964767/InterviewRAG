"""管理端：评估报告接口

GET /api/admin/eval/summary  — 评估汇总
GET /api/admin/eval/detail   — 评估详情
"""

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_admin import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "results"
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$")


def _normalize_history_item(data: dict, filename: str) -> dict:
    stem = filename.removesuffix(".json")
    parts = stem.split("T", 1)
    if len(parts) == 2:
        time_part = parts[1].replace("-", ":")
        ts = f"{parts[0]}T{time_part}"
    else:
        ts = stem
    return {
        "metrics": data.get("aggregated", {}),
        "timestamp": ts,
        "total": data.get("total", 0),
        "error_count": len(data.get("errors", [])),
    }


@router.get("/eval/summary")
async def eval_summary():
    """返回最新评估汇总 + 历史快照列表"""
    latest_path = RESULTS_DIR / "latest_summary.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    else:
        latest = None

    history_dir = RESULTS_DIR / "history"
    history: list[dict] = []
    if history_dir.is_dir():
        for fp in sorted(history_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                history.append(_normalize_history_item(data, fp.name))
            except Exception:
                continue

    return {"latest": latest, "history": history}


@router.get("/eval/detail")
async def eval_detail(ts: str | None = None):
    """返回完整评估结果（latest 或指定历史快照）"""
    if ts:
        if not _TS_RE.match(ts):
            raise HTTPException(status_code=400, detail="ts 参数格式无效")
        file_path = RESULTS_DIR / "history" / f"{ts}.json"
    else:
        file_path = RESULTS_DIR / "latest.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="未找到该评估结果")

    return json.loads(file_path.read_text(encoding="utf-8"))
