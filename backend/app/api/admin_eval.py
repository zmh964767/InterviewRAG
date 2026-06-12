"""管理端：评估报告接口

GET  /api/admin/eval/summary  — 评估汇总
GET  /api/admin/eval/detail   — 评估详情
POST /api/admin/eval/run      — 异步触发评估
POST /api/admin/eval/cancel   — 取消正在运行的评估
GET  /api/admin/eval/tasks    — 列出评估任务
GET  /api/admin/eval/compare  — 两快照指标对比
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps_admin import require_admin
from app.services.task_store import store as task_store

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "results"
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}[-:]\d{2}[-:]\d{2}$")

# 存储正在运行的 asyncio 任务引用，用于取消
_running_eval_tasks: dict[str, asyncio.Task] = {}


def _normalize_history_item(data: dict, filename: str) -> dict:
    """将 history/*.json 文件转为前端展示格式，timestamp 始终用文件名"""
    stem = filename.removesuffix(".json")
    # 文件名是 "2026-06-08T23-26-02" 短横线格式，始终作为 timestamp
    return {
        "metrics": data.get("aggregated", {}),
        "timestamp": stem,
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


class RunEvalRequest(BaseModel):
    mode: str = "full"  # "full" | "ragas" | "comparison" | "sanity"


@router.post("/eval/run")
async def run_eval_endpoint(request: RunEvalRequest):
    """异步触发评估任务（限流：已有 running 时拒绝）"""
    if request.mode not in ("full", "ragas", "comparison", "sanity"):
        raise HTTPException(status_code=400, detail=f"不支持的 mode: {request.mode}")

    if task_store.list_active():
        raise HTTPException(status_code=409, detail="已有评估任务在进行中")

    task = task_store.create("eval", f"mode={request.mode}")
    _async_task = asyncio.create_task(_run_eval_task(task.task_id, request.mode))
    _running_eval_tasks[task.task_id] = _async_task
    return {"task_id": task.task_id}


@router.post("/eval/cancel")
async def cancel_eval_endpoint():
    """取消正在运行的评估任务"""
    active = task_store.list_active()
    if not active:
        raise HTTPException(status_code=404, detail="没有正在运行的评估任务")

    cancelled = 0
    for t in active:
        task_ref = _running_eval_tasks.pop(t.task_id, None)
        if task_ref:
            task_ref.cancel()
        task_store.update(t.task_id, status="failed", error_message="用户取消", finished_at=datetime.now().isoformat())
        cancelled += 1

    return {"cancelled": cancelled}


# 参与对比的 4 个 RAGAS 指标
_COMPARE_METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


@router.get("/eval/compare")
async def eval_compare(
    base: str = Query(..., description="base 快照时间戳,或 'latest'"),
    target: str = Query(..., description="target 快照时间戳,或 'latest'"),
):
    """对比两个评估快照的 RAGAS 指标

    ts 支持 "latest" 关键字指向 latest.json,或合法的时间戳字符串。
    """
    from app.models.schemas import CompareResponse, MetricDiff
    from evaluation.regression import REGRESSION_THRESHOLD

    def _resolve_path(ts: str) -> Path:
        if ts == "latest":
            return RESULTS_DIR / "latest.json"
        if not _TS_RE.match(ts):
            raise HTTPException(status_code=400, detail="ts 参数格式无效")
        return RESULTS_DIR / "history" / f"{ts}.json"

    base_path = _resolve_path(base)
    target_path = _resolve_path(target)
    if not base_path.exists():
        raise HTTPException(status_code=404, detail=f"未找到 base 快照: {base}")
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"未找到 target 快照: {target}")

    base_data = json.loads(base_path.read_text(encoding="utf-8"))
    target_data = json.loads(target_path.read_text(encoding="utf-8"))

    base_metrics = base_data.get("aggregated", {}) or {}
    target_metrics = target_data.get("aggregated", {}) or {}

    diffs: list[MetricDiff] = []
    for metric in _COMPARE_METRICS:
        b = float(base_metrics.get(metric, 0) or 0)
        t = float(target_metrics.get(metric, 0) or 0)
        change = t - b
        if abs(change) < REGRESSION_THRESHOLD:
            direction = "same"
        elif change > 0:
            direction = "up"
        else:
            direction = "down"
        diffs.append(MetricDiff(name=metric, base=b, target=t, change=round(change, 4), direction=direction))

    improved = sum(1 for d in diffs if d.direction == "up")
    regressed = sum(1 for d in diffs if d.direction == "down")
    same = sum(1 for d in diffs if d.direction == "same")

    def _summary(d: dict, fallback_ts: str) -> dict:
        return {
            "timestamp": d.get("timestamp", fallback_ts),
            "total": d.get("total", 0),
            "error_count": len(d.get("errors", []) or []),
            "metrics": d.get("aggregated", {}) or {},
        }

    return CompareResponse(
        base=_summary(base_data, base),
        target=_summary(target_data, target),
        diffs=diffs,
        improved=improved,
        regressed=regressed,
        same=same,
    )


@router.get("/eval/tasks")
async def list_eval_tasks():
    """列出所有评估任务（用于前端轮询）"""
    from app.models.schemas import TaskListResponse
    tasks = task_store.list_all() if hasattr(task_store, "list_all") else task_store.list_active()
    eval_tasks = [t for t in tasks if t.source_type == "eval"]
    return TaskListResponse(tasks=[{
        "task_id": t.task_id,
        "status": t.status,
        "source_type": t.source_type,
        "source": t.source,
        "total": t.total,
        "done": t.done,
        "ingested": t.ingested,
        "duplicates": t.duplicates,
        "errors": t.errors,
        "started_at": t.started_at,
        "finished_at": t.finished_at,
        "error_message": t.error_message,
    } for t in eval_tasks])


async def _run_eval_task(task_id: str, mode: str) -> None:
    """后台执行评估任务"""
    task_store.update(task_id, status="running")
    try:
        from evaluation.run import load_eval_dataset
        from evaluation.runner import run_ragas_evaluation, run_comparison_evaluation, EvalSummary
        from evaluation.regression import save_results

        items = load_eval_dataset()
        if not items:
            raise RuntimeError("评估数据集为空")

        # 跑 RAGAS（如需要）
        if mode in ("full", "ragas", "sanity"):
            def _on_progress(done, total):
                task_store.update(task_id, total=total, done=done)
            logger.info(f"[eval] 开始 RAG 查询，{len(items)} 题...")
            summary = await run_ragas_evaluation(items, progress_callback=_on_progress)
            logger.info(f"[eval] RAGAS 评估完成，aggregated={summary.aggregated}")
        else:
            summary = EvalSummary(results=[], aggregated={}, errors=[], error_rate=0)

        # 跑 comparison（如需要）
        if mode in ("full", "comparison"):
            logger.info(f"[eval] 开始策略对比...")
            comparison = await run_comparison_evaluation(items)
            logger.info(f"[eval] 策略对比完成")
        else:
            comparison = {}

        # 保存结果
        logger.info(f"[eval] 保存结果...")
        save_results(summary=summary, comparison=comparison, results_dir=RESULTS_DIR)
        logger.info(f"[eval] 保存完成")

        task_store.update(
            task_id,
            status="done",
            finished_at=datetime.now().isoformat(),
        )
        logger.info(f"评估任务 {task_id} 完成")
    except asyncio.CancelledError:
        task_store.update(task_id, status="failed", error_message="用户取消", finished_at=datetime.now().isoformat())
    except Exception as e:
        logger.error(f"评估任务 {task_id} 失败: {e}", exc_info=True)
        task_store.update(
            task_id,
            status="failed",
            error_message=str(e),
            finished_at=datetime.now().isoformat(),
        )
