"""评估报告接口"""

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/eval", tags=["eval"])

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "results"
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$")


def _normalize_history_item(data: dict, filename: str) -> dict:
    """将 history 快照（full detail 形式）转换为 summary 形式供前端列表使用。

    历史文件实际结构: { aggregated, errors, total, comparison }
    需要输出: { metrics, timestamp, total, error_count }

    文件名格式: 2026-06-08T23-26-02.json → timestamp: 2026-06-08T23:26:02
    """
    stem = filename.removesuffix(".json")  # 2026-06-08T23-26-02
    # Split at 'T' to separate date and time parts
    parts = stem.split("T", 1)
    if len(parts) == 2:
        # time part: 23-26-02 → 23:26:02 (replace dashes with colons)
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


@router.get("/summary")
async def eval_summary():
    """返回最新评估汇总 + 历史快照列表"""
    # latest summary
    latest_path = RESULTS_DIR / "latest_summary.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    else:
        latest = None

    # history snapshots — normalize from full detail shape to summary shape
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


@router.get("/detail")
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
