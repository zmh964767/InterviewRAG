"""评估报告生成器

生成终端摘要 + Markdown 报告。
"""

from datetime import datetime
from pathlib import Path


def generate_terminal_summary(
    aggregated: dict,
    errors: list[str],
    total: int,
    comparison: dict | None = None,
) -> str:
    """生成终端可打印的摘要"""
    lines = []
    lines.append("=" * 60)
    lines.append("RAG 评估摘要")
    lines.append("=" * 60)

    if aggregated:
        lines.append("【RAGAS 指标】")
        for metric, value in aggregated.items():
            lines.append(f"  {metric:25s}: {value:.4f}")

    if comparison:
        lines.append("")
        lines.append("【检索策略对比】")
        for plan_name, metrics in comparison.items():
            hr = metrics.get("hit_rate@5", 0)
            mrr_v = metrics.get("mrr", 0)
            lines.append(f"  {plan_name:25s}  HR@5={hr:.4f}  MRR={mrr_v:.4f}")

    lines.append("")
    success = total - len(errors)
    lines.append(f"  成功: {success}  失败: {len(errors)}  总计: {total}")
    if errors:
        error_rate = len(errors) / total if total else 0
        if error_rate > 0.2:
            lines.append(f"  ⚠️  失败率 {error_rate:.0%} > 20%，结果可能不可靠")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(
    aggregated: dict,
    errors: list[str],
    total: int,
    comparison: dict | None = None,
    output_path: Path | None = None,
) -> str:
    """生成 Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# RAG 评估报告 — {now}", ""]

    if aggregated:
        lines.append("## RAGAS 指标")
        lines.append("")
        lines.append("| 指标 | 分值 |")
        lines.append("|---|---|")
        for metric, value in sorted(aggregated.items()):
            lines.append(f"| {metric} | {value:.4f} |")
        lines.append("")

    if comparison:
        lines.append("## 检索策略对比")
        lines.append("")
        lines.append("| 方案 | Hit Rate@5 | MRR |")
        lines.append("|---|---|---|")
        for plan_name, metrics in comparison.items():
            hr = metrics.get("hit_rate@5", 0)
            mrr_v = metrics.get("mrr", 0)
            lines.append(f"| {plan_name} | {hr:.4f} | {mrr_v:.4f} |")
        lines.append("")

    if errors:
        lines.append(f"## 失败案例（{len(errors)} 道）")
        lines.append("")
        for err_id in errors:
            lines.append(f"- `{err_id}`")
        lines.append("")

    lines.append("---")
    success = total - len(errors)
    lines.append(f"成功 {success} / 失败 {len(errors)} / 总计 {total}")

    content = "\n".join(lines) + "\n"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    return content
