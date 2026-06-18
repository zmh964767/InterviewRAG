"""回归检测

比较本次评估结果与历史结果，检测指标波动。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

REGRESSION_THRESHOLD = 0.05  # 5% 波动阈值


def save_results(summary, comparison: dict, results_dir: Path, tag: str | None = None) -> None:
    """保存结果到 latest.json + history/<timestamp>.json

    每次运行都会把上次的 latest.json 备份到 history/，再写新的 latest.json。

    Args:
        summary: EvalSummary 或 dict
        comparison: 检索对比结果
        results_dir: 结果目录
        tag: 可选标记（如 "fast"），写入 payload 方便区分
    """
    from dataclasses import asdict, is_dataclass
    results_dir.mkdir(parents=True, exist_ok=True)
    history_dir = results_dir / "history"
    history_dir.mkdir(exist_ok=True)

    # 兼容 dict 和 EvalSummary dataclass
    if is_dataclass(summary):
        summary_dict = asdict(summary)
    else:
        summary_dict = summary

    ts = datetime.now().isoformat(timespec="seconds").replace(":", "-")

    latest_path = results_dir / "latest.json"
    if latest_path.exists():
        backup = history_dir / f"{ts}.json"
        shutil.copy2(latest_path, backup)

    # 构造完整 payload（含 items 详情）
    items = summary_dict.get("results", [])
    payload = {
        "timestamp": ts,
        "tag": tag,
        "sample_size": len(items) if tag else None,
        "aggregated": summary_dict.get("aggregated", {}),
        "errors": summary_dict.get("errors", []),
        "total": len(items),
        "items": [
            {
                "id": r["id"],
                "question": r.get("question", ""),
                "answer": r.get("answer", ""),
                "metrics": r.get("metrics", {}),
                "error": r.get("error"),
            }
            for r in items
        ],
        "comparison": comparison,
    }
    latest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_path = results_dir / "latest_summary.json"
    summary_only = {
        "metrics": summary_dict.get("aggregated", {}),
        "error_count": len(summary_dict.get("errors", [])),
        "total": len(items),
        "timestamp": datetime.now().isoformat(),
    }
    summary_path.write_text(
        json.dumps(summary_only, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def check_regression(
    current_metrics: dict,
    results_dir: Path,
) -> list[dict]:
    """比较本次与上一次结果

    Returns:
        [{"metric": str, "old": float, "new": float, "change": float,
          "regression": bool, "improvement": bool}, ...]
    """
    latest_path = results_dir / "latest.json"
    if not latest_path.exists():
        return []

    previous = json.loads(latest_path.read_text(encoding="utf-8"))
    previous_metrics = previous.get("aggregated", {})

    changes = []
    for metric, new_val in current_metrics.items():
        old_val = previous_metrics.get(metric)
        if old_val is None:
            continue
        change = new_val - old_val
        changes.append({
            "metric": metric,
            "old": round(old_val, 4),
            "new": round(new_val, 4),
            "change": round(change, 4),
            "regression": change < -REGRESSION_THRESHOLD,
            "improvement": change > REGRESSION_THRESHOLD,
        })

    return changes
