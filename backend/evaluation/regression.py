"""回归检测

比较本次评估结果与历史结果，检测指标波动。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

REGRESSION_THRESHOLD = 0.05  # 5% 波动阈值


def save_results(summary_dict: dict, results_dir: Path) -> None:
    """保存结果到 latest.json + history/<timestamp>.json

    每次运行都会把上次的 latest.json 备份到 history/，再写新的 latest.json。
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    history_dir = results_dir / "history"
    history_dir.mkdir(exist_ok=True)

    latest_path = results_dir / "latest.json"
    if latest_path.exists():
        ts = datetime.now().isoformat(timespec="seconds").replace(":", "-")
        backup = history_dir / f"{ts}.json"
        shutil.copy2(latest_path, backup)

    latest_path.write_text(
        json.dumps(summary_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_path = results_dir / "latest_summary.json"
    summary_only = {
        "metrics": summary_dict.get("aggregated", {}),
        "error_count": len(summary_dict.get("errors", [])),
        "total": summary_dict.get("total", 0),
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
