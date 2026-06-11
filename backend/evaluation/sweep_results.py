"""Sweep 结果汇总

从 sweep/ 下 json 文件生成：
- sweep_summary.csv: 9 行（5P + 4C），列：type/variant/chunk_size/E_hr5/E_mrr/B_hr5
- WINNER.md: 最优组合 + 落地建议
"""

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_rows(sweep_dir: Path) -> list[dict]:
    """扫 sweep/ 下所有 json，按 type 归类构造行。"""
    rows: list[dict] = []

    # Prompt sweep 结果
    for v in [1, 2, 3, 4, 5]:
        path = sweep_dir / f"prompt_v{v}.json"
        if not path.exists():
            continue
        d = _read_json(path)
        comp = d.get("comparison", {})
        rows.append({
            "type": "prompt",
            "variant": d.get("prompt_variant"),
            "chunk_size": d.get("chunk_size"),
            "E_hr5": comp.get("E_多路改写混合", {}).get("hit_rate@5", 0.0),
            "E_mrr": comp.get("E_多路改写混合", {}).get("mrr", 0.0),
            "B_hr5": comp.get("B_混合检索", {}).get("hit_rate@5", 0.0),
            "B_mrr": comp.get("B_混合检索", {}).get("mrr", 0.0),
            "duration_s": d.get("duration_s"),
        })

    # Chunk sweep 结果
    for size in [200, 500, 800, 1200]:
        path = sweep_dir / f"chunk_{size}.json"
        if not path.exists():
            continue
        d = _read_json(path)
        comp = d.get("comparison", {})
        rows.append({
            "type": "chunk",
            "variant": d.get("prompt_variant"),
            "chunk_size": d.get("chunk_size"),
            "E_hr5": comp.get("E_多路改写混合", {}).get("hit_rate@5", 0.0),
            "E_mrr": comp.get("E_多路改写混合", {}).get("mrr", 0.0),
            "B_hr5": comp.get("B_混合检索", {}).get("hit_rate@5", 0.0),
            "B_mrr": comp.get("B_混合检索", {}).get("mrr", 0.0),
            "duration_s": d.get("duration_s"),
        })

    return rows


def generate_summary_csv(sweep_dir: Path) -> Path:
    """生成 sweep_summary.csv。"""
    rows = _build_rows(sweep_dir)
    out = sweep_dir / "sweep_summary.csv"
    fieldnames = [
        "type", "variant", "chunk_size",
        "E_hr5", "E_mrr", "B_hr5", "B_mrr", "duration_s",
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"sweep_summary.csv: {len(rows)} 行 → {out}")
    return out


def _find_winner(rows: list[dict]) -> dict | None:
    """从所有行里挑 E_hr5 最高的作为 WINNER。"""
    if not rows:
        return None
    return max(rows, key=lambda r: r.get("E_hr5", 0.0))


def generate_winner_md(sweep_dir: Path, baseline_e_hr5: float = 0.3529) -> Path:
    """生成 WINNER.md：最优组合 + 落地建议。"""
    rows = _build_rows(sweep_dir)
    winner = _find_winner(rows)
    out = sweep_dir / "WINNER.md"

    if not winner:
        out.write_text("# WINNER\n\n无 sweep 结果\n", encoding="utf-8")
        return out

    improvement = (winner["E_hr5"] - baseline_e_hr5) / baseline_e_hr5
    prompt_only = [r for r in rows if r["type"] == "prompt"]
    chunk_only = [r for r in rows if r["type"] == "chunk"]
    best_prompt = (
        max(prompt_only, key=lambda r: r["E_hr5"]) if prompt_only else None
    )
    best_chunk = (
        max(chunk_only, key=lambda r: r["E_hr5"]) if chunk_only else None
    )

    # 预计算（避免 f-string 内三元表达式在格式化时的歧义）
    bp_variant = best_prompt['variant'] if best_prompt else 'N/A'
    bp_hr5 = f"{best_prompt['E_hr5']:.4f}" if best_prompt else 'N/A'
    bc_size = best_chunk['chunk_size'] if best_chunk else 'N/A'
    bc_hr5 = f"{best_chunk['E_hr5']:.4f}" if best_chunk else 'N/A'
    recommended_variant = winner['variant'] if winner['type'] == 'prompt' else (best_prompt['variant'] if best_prompt else 1)

    md = f"""# WINNER

**Sweep 时间**: {datetime_str(sweep_dir)}
**基线 (sweep 前 strategy E HR@5)**: {baseline_e_hr5:.4f}

## 总冠军

| 字段 | 值 |
|------|----|
| type | {winner['type']} |
| variant | {winner['variant']} |
| chunk_size | {winner['chunk_size']} |
| **E HR@5** | **{winner['E_hr5']:.4f}** |
| E MRR | {winner['E_mrr']:.4f} |
| B HR@5 (单路基线) | {winner['B_hr5']:.4f} |
| 相对 sweep 前提升 | {improvement:+.1%} |

## 单变量最优

- **最优 Prompt variant**: {bp_variant} (E HR@5 = {bp_hr5})
- **最优 chunk_size**: {bc_size} (E HR@5 = {bc_hr5})

## 落地建议

1. 更新 `backend/app/config.py`:
   - `query_rewrite_prompt_variant` → {recommended_variant}
2. 设置 `CHUNK_SIZE` 环境变量 → {winner['chunk_size']}
3. reingest: `python -c "from evaluation.reingest import reingest_with_chunk_size; reingest_with_chunk_size({winner['chunk_size']})"`
4. 跑一次完整 comparison 验证：`python -m evaluation.run --mode comparison`

## 顺序假设说明

本次 sweep 是**单变量顺序**（先 Prompt 后 Chunk），隐含假设：
**Prompt 变体不会因 chunk_size 变化而效果反转**。
如有怀疑，可跑 2D 网格 sweep 验证，但成本 ×4。

## 完整结果

见 `sweep_summary.csv`。
"""
    out.write_text(md, encoding="utf-8")
    logger.info(f"WINNER.md → {out}")
    return out


def datetime_str(sweep_dir: Path) -> str:
    """从最新 json 的 timestamp 字段取时间。"""
    candidates = list(sweep_dir.glob("*.json"))
    if not candidates:
        return "unknown"
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    d = _read_json(candidates[0])
    return d.get("timestamp", "unknown")
