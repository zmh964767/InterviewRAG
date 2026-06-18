"""评估 CLI 入口

用法：
  python -m evaluation.run                    # 完整评估（254 题）
  python -m evaluation.run --mode fast        # 快速评估（分层抽样 ~20 题，~3 分钟）
  python -m evaluation.run --mode ragas       # 只跑 RAGAS（全量）
  python -m evaluation.run --mode comparison  # 只跑检索对比
  python -m evaluation.run --mode sanity      # 快速 sanity check
  python -m evaluation.run --sample 30        # 抽样 30 题（配合 --mode ragas/full）
  python -m evaluation.run --skip-regression  # 跳过回归检测
  python -m evaluation.run --verbose          # 详细输出
"""

import argparse
import asyncio
import json
import logging
import random
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

RESULTS_DIR_NAME = "results"

# fast 模式默认抽样数
FAST_SAMPLE_SIZE = 20


def load_eval_dataset() -> list[dict]:
    """加载评估数据集，过滤掉 irrelevant 类型"""
    eval_path = Path(__file__).parent / "eval_dataset.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"评估数据集不存在: {eval_path}")
    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    return [item for item in eval_data if item.get("type") != "irrelevant"]


def stratified_sample(items: list[dict], n: int, seed: int = 42) -> list[dict]:
    """分层抽样：按 type 比例抽取 n 题，保证每种题型至少 1 题

    Args:
        items: 评估题列表（已过滤 irrelevant）
        n: 目标抽样数
        seed: 随机种子（可复现）

    Returns:
        抽样后的子集
    """
    rng = random.Random(seed)

    # 按 type 分组
    by_type: dict[str, list[dict]] = {}
    for item in items:
        t = item.get("type", "unknown")
        by_type.setdefault(t, []).append(item)

    # 按比例分配，每种至少 1 题
    total = len(items)
    sampled: list[dict] = []
    remaining = n

    types = sorted(by_type.keys())
    for i, t in enumerate(types):
        group = by_type[t]
        if i == len(types) - 1:
            # 最后一种：用完剩余配额
            quota = min(remaining, len(group))
        else:
            quota = max(1, round(n * len(group) / total))
            quota = min(quota, len(group), remaining)
        sampled.extend(rng.sample(group, quota))
        remaining -= quota
        if remaining <= 0:
            break

    # 如果还有剩余配额（因为四舍五入），从未抽满的类型中补
    if remaining > 0:
        used_ids = {s["id"] for s in sampled}
        pool = [item for item in items if item["id"] not in used_ids]
        if pool:
            sampled.extend(rng.sample(pool, min(remaining, len(pool))))

    rng.shuffle(sampled)
    return sampled


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 评估工具")
    parser.add_argument(
        "--mode",
        choices=["full", "ragas", "comparison", "sanity", "fast"],
        default="full",
        help="评估模式（默认 full）；fast = 分层抽样 + RAGAS + 对比（~3 分钟）",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="抽样题数（配合 ragas/full 模式使用；fast 模式默认 20）",
    )
    parser.add_argument("--skip-regression", action="store_true", help="跳过回归检测")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s | %(message)s")

    # 强制 stdout 行缓冲，确保后台任务（如 Claude Code background）能看到实时日志
    sys.stdout.reconfigure(line_buffering=True)

    # 1. 前置检查
    from app.config import get_settings
    settings = get_settings()
    if not settings.zhipu_api_key:
        print("[ERR] 缺少 ZHIPU_API_KEY，请在 .env 中配置", file=sys.stderr)
        return 1

    # 2. 加载数据集
    eval_path = Path(__file__).parent / "eval_dataset.json"
    if not eval_path.exists():
        print(f"[ERR] 数据集不存在: {eval_path}", file=sys.stderr)
        return 1

    eval_items = load_eval_dataset()
    if not eval_items:
        print("[ERR] 评估数据集为空", file=sys.stderr)
        return 1

    # fast 模式：分层抽样
    is_fast = args.mode == "fast"
    if is_fast:
        sample_n = args.sample or FAST_SAMPLE_SIZE
        eval_items = stratified_sample(eval_items, sample_n)
        type_dist = {}
        for item in eval_items:
            t = item.get("type", "unknown")
            type_dist[t] = type_dist.get(t, 0) + 1
        logger.info(f"🚀 快速模式：分层抽样 {len(eval_items)} 题（{type_dist}）")
    elif args.sample:
        eval_items = stratified_sample(eval_items, args.sample)
        logger.info(f"抽样 {len(eval_items)} 题")

    logger.info(f"加载 {len(eval_items)} 道评估题（模式: {args.mode}）")

    # 3. 准备结果目录
    results_dir = Path(__file__).parent / RESULTS_DIR_NAME
    report_path = Path(__file__).parent / "report.md"

    # 4. 执行评估
    ragas_summary = None
    comparison_results = None

    # fast 模式跑 ragas + comparison（但用抽样数据）
    effective_mode = "full" if is_fast else args.mode

    if effective_mode in ("full", "ragas"):
        from evaluation.runner import run_ragas_evaluation
        ragas_summary = asyncio.run(run_ragas_evaluation(eval_items))

    if effective_mode in ("full", "comparison"):
        from evaluation.runner import run_comparison_evaluation
        comparison_results = asyncio.run(run_comparison_evaluation(eval_items))

    if args.mode == "sanity":
        # sanity 模式：跑一个最简查询确认整条链路通畅
        from app.services.rag_service import RAGService
        rag = RAGService()
        result = asyncio.run(rag.query("什么是 Transformer？"))
        print("\n=== Sanity Check ===")
        print(f"Answer 长度: {len(result.get('answer', ''))}")
        print(f"Sources: {len(result.get('sources', []))}")
        if result.get("answer"):
            print("[OK] Sanity passed")
            return 0
        else:
            print("[FAIL] Sanity failed: empty answer")
            return 1

    # 5. 报告生成
    from evaluation.reporter import generate_markdown_report, generate_terminal_summary
    from evaluation.regression import check_regression, save_results

    aggregated = ragas_summary.aggregated if ragas_summary else {}
    errors = ragas_summary.errors if ragas_summary else []
    total = len(eval_items)

    mode_label = "🚀 快速评估" if is_fast else "📊 完整评估"
    print(f"\n{'='*60}")
    print(f"{mode_label}（{total} 题）")
    print(f"{'='*60}")

    # 终端摘要
    print(generate_terminal_summary(aggregated, errors, total, comparison_results))

    # Markdown 报告
    md = generate_markdown_report(aggregated, errors, total, comparison_results, report_path)
    logger.info(f"Markdown 报告已生成: {report_path}")

    # 6. 回归检测（fast 模式跳过，因为抽样数据不适合回归对比）
    if not args.skip_regression and not is_fast and aggregated:
        changes = check_regression(aggregated, results_dir)
        if changes:
            print("\n=== 回归检测 ===")
            for ch in changes:
                flag = "[REGR]" if ch["regression"] else ("[IMPR]" if ch["improvement"] else "     ")
                print(f"  {flag}{ch['metric']:25s}  {ch['old']:.4f} → {ch['new']:.4f}  ({ch['change']:+.4f})")
            if any(ch["regression"] for ch in changes):
                print("\n[REGR] 检测到 RAG 质量回归（指标下降 > 5%）")
                return 1  # exit 1 触发 CI 失败
        else:
            print("\n[OK] 无历史结果可对比（首次评估）")
    elif is_fast:
        logger.info("快速模式跳过回归检测（抽样数据不适合纵向对比）")

    # 7. 持久化（fast 模式也保存，但标记为 fast）
    if aggregated:
        save_results(
            ragas_summary,
            comparison_results or {},
            results_dir,
            tag="fast" if is_fast else None,
        )
        logger.info(f"结果已保存: {results_dir / 'latest.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
