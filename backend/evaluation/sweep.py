"""单变量 Sweep 驱动

调优检索链路参数（Prompt variant + Chunk size）：

阶段 1: Prompt sweep（chunk_size 固定 500）
  遍历 5 个 prompt variant，存 sweep/prompt_v{1..5}.json

阶段 2: Chunk sweep（prompt_variant = 阶段 1 最优）
  遍历 4 个 chunk_size，reingest 后存 sweep/chunk_{200,500,800,1200}.json

阶段 3: 汇总
  sweep_summary.csv + WINNER.md

Usage:
    cd backend && python -m evaluation.sweep
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from evaluation.reingest import reingest_with_chunk_size
from evaluation.runner import run_comparison_evaluation

logger = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).parent
EVAL_DATASET_PATH = EVAL_DIR / "eval_dataset.json"
SWEEP_DIR = EVAL_DIR / "results" / "sweep"

PROMPT_VARIANTS = [1, 2, 3, 4, 5]
CHUNK_SIZES = [200, 500, 800, 1200]
DEFAULT_CHUNK_SIZE = 500
BASELINE_E_HR5 = 0.3529  # sweep 前基线（commit 2fb19a0 跑出的 B 行为）


def _load_eval_items() -> list[dict]:
    data = json.loads(EVAL_DATASET_PATH.read_text(encoding="utf-8"))
    return [i for i in data if i.get("type") != "irrelevant"]


def _extract_e_hr5(comparison: dict) -> float:
    e = comparison.get("E_多路改写混合", {})
    return e.get("hit_rate@5", 0.0)


def _save_result(name: str, result: dict) -> Path:
    """存单组结果到 sweep/{name}.json"""
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    out = SWEEP_DIR / f"{name}.json"
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


async def _run_one(prompt_variant: int, chunk_size: int) -> dict:
    """跑一组：(prompt_variant, chunk_size) → 调 runner + 计时。"""
    start = time.time()
    # 临时覆盖 chunk_size（lru_cache 已被 env 注入触发重建）
    os.environ["CHUNK_SIZE"] = str(chunk_size)
    get_settings.cache_clear()
    # prompt_variant 通过 settings 传（不能 env 注入 int 安全范围 1..5 走构造参数更稳）
    os.environ["QUERY_REWRITE_PROMPT_VARIANT"] = str(prompt_variant)
    get_settings.cache_clear()

    eval_items = _load_eval_items()
    comparison = await run_comparison_evaluation(eval_items)

    elapsed = round(time.time() - start, 1)
    return {
        "prompt_variant": prompt_variant,
        "chunk_size": chunk_size,
        "timestamp": datetime.now().isoformat(),
        "duration_s": elapsed,
        "comparison": comparison,
    }


def _pick_best_prompt() -> int:
    """从 sweep/prompt_v*.json 里挑 E HR@5 最高的 variant。"""
    candidates = []
    for v in PROMPT_VARIANTS:
        path = SWEEP_DIR / f"prompt_v{v}.json"
        if not path.exists():
            logger.warning(f"阶段 1 缺结果: {path}")
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        candidates.append((v, _extract_e_hr5(d.get("comparison", {}))))
    if not candidates:
        raise RuntimeError("Prompt sweep 结果为空")
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_v, best_hr5 = candidates[0]
    logger.info(
        f"阶段 1 最优 prompt_variant={best_v} (E HR@5={best_hr5:.4f})"
    )
    return best_v


async def main() -> None:
    """主流程：阶段 1 → 阶段 2 → 阶段 3。"""
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    eval_items = _load_eval_items()
    logger.info(f"加载 {len(eval_items)} 道评估题")

    # 阶段 1: Prompt sweep（chunk_size 固定 500）
    logger.info("=" * 60)
    logger.info("阶段 1: Prompt sweep（chunk_size 固定 500）")
    logger.info("=" * 60)
    for v in PROMPT_VARIANTS:
        logger.info(f"--- Prompt variant {v} ---")
        result = await _run_one(prompt_variant=v, chunk_size=DEFAULT_CHUNK_SIZE)
        path = _save_result(f"prompt_v{v}", result)
        e_hr5 = _extract_e_hr5(result["comparison"])
        logger.info(
            f"saved {path.name}: E HR@5={e_hr5:.4f}, "
            f"duration={result['duration_s']}s"
        )

    # 阶段 2: Chunk sweep（prompt_variant 用阶段 1 最优）
    best_prompt = _pick_best_prompt()
    logger.info("=" * 60)
    logger.info(
        f"阶段 2: Chunk sweep（prompt_variant={best_prompt}）"
    )
    logger.info("=" * 60)
    for size in CHUNK_SIZES:
        logger.info(f"--- Chunk size {size} ---")
        # reingest 必须先于 evaluation，否则 ChromaDB 仍是旧 chunk_size
        reingest_info = reingest_with_chunk_size(size)
        logger.info(f"reingest: {reingest_info}")
        result = await _run_one(prompt_variant=best_prompt, chunk_size=size)
        path = _save_result(f"chunk_{size}", result)
        e_hr5 = _extract_e_hr5(result["comparison"])
        logger.info(
            f"saved {path.name}: E HR@5={e_hr5:.4f}, "
            f"duration={result['duration_s']}s"
        )

    # 阶段 3: 汇总
    from evaluation.sweep_results import generate_summary_csv, generate_winner_md

    generate_summary_csv(SWEEP_DIR)
    generate_winner_md(SWEEP_DIR)
    logger.info("=" * 60)
    logger.info("Sweep 完成，结果见:")
    logger.info(f"  {SWEEP_DIR / 'sweep_summary.csv'}")
    logger.info(f"  {SWEEP_DIR / 'WINNER.md'}")
    logger.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(main())
