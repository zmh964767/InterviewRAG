"""评估 CLI 入口

用法：
  python -m evaluation.run                    # 完整评估
  python -m evaluation.run --mode ragas       # 只跑 RAGAS
  python -m evaluation.run --mode comparison  # 只跑检索对比
  python -m evaluation.run --mode sanity      # 快速 sanity check
  python -m evaluation.run --skip-regression  # 跳过回归检测
  python -m evaluation.run --verbose          # 详细输出
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

RESULTS_DIR_NAME = "results"


def load_eval_dataset() -> list[dict]:
    """加载评估数据集，过滤掉 irrelevant 类型"""
    eval_path = Path(__file__).parent / "eval_dataset.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"评估数据集不存在: {eval_path}")
    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    return [item for item in eval_data if item.get("type") != "irrelevant"]


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 评估工具")
    parser.add_argument(
        "--mode",
        choices=["full", "ragas", "comparison", "sanity"],
        default="full",
        help="评估模式（默认 full）",
    )
    parser.add_argument("--skip-regression", action="store_true", help="跳过回归检测")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s | %(message)s")

    # 强制 stdout 行缓冲，确保后台任务（如 Claude Code background）能看到实时日志
    import sys
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

    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    eval_items = [item for item in eval_data if item.get("type") != "irrelevant"]
    if not eval_items:
        print("[ERR] 评估数据集为空", file=sys.stderr)
        return 1

    logger.info(f"加载 {len(eval_items)} 道评估题（模式: {args.mode}）")

    # 3. 准备结果目录
    results_dir = Path(__file__).parent / RESULTS_DIR_NAME
    report_path = Path(__file__).parent / "report.md"

    # 4. 执行评估
    ragas_summary = None
    comparison_results = None

    if args.mode in ("full", "ragas"):
        from evaluation.runner import run_ragas_evaluation
        ragas_summary = asyncio.run(run_ragas_evaluation(eval_items))

    if args.mode in ("full", "comparison"):
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

    # 终端摘要
    print(generate_terminal_summary(aggregated, errors, total, comparison_results))

    # Markdown 报告
    md = generate_markdown_report(aggregated, errors, total, comparison_results, report_path)
    logger.info(f"Markdown 报告已生成: {report_path}")

    # 6. 回归检测
    if not args.skip_regression and aggregated:
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

    # 7. 持久化
    if aggregated:
        save_results(
            ragas_summary,
            comparison_results or {},
            results_dir,
        )
        logger.info(f"结果已保存: {results_dir / 'latest.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
