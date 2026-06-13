"""评估数据集验证脚本

验证数据集格式 + 覆盖度。

用法：
  cd D:/Zerobyheart/InterviewRAG/backend
  python -m evaluation.validate_dataset                           # 验证默认路径
  python -m evaluation.validate_dataset --file path/to/file.json  # 验证指定文件
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = ["id", "type", "question", "ground_truth", "category", "source"]
# 已知的生产类型：exact（知识库原题）, paraphrase（口语化改写）, complex（多知识点综合）
# cross_category（跨类别）为预留扩展类型，生成脚本暂未输出
VALID_TYPES = {"exact", "paraphrase", "complex", "cross_category", "irrelevant"}
MIN_TOTAL = 100
MIN_CATEGORIES = 3
MIN_PER_CATEGORY = 10


def validate_dataset(filepath: str) -> bool:
    """验证数据集，返回 True 表示通过"""
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: 文件不存在: {filepath}")
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON 解析失败: {e}")
        return False

    if not isinstance(data, list):
        print("ERROR: 数据集应为 JSON 数组")
        return False

    errors = []
    warnings = []

    # 1. 检查总数
    total = len(data)
    print(f"总问题数: {total}")
    if total < MIN_TOTAL:
        errors.append(f"总问题数不足: {total} < {MIN_TOTAL}")

    # 2. 按类型统计
    type_counts = Counter(item.get("type", "missing") for item in data)
    print(f"\n类型分布:")
    for t, n in sorted(type_counts.items()):
        marker = "  " if t in VALID_TYPES else " [未知类型]"
        print(f"  {t}: {n}{marker}")

    # 检查必需类型存在
    non_irrelevant_types = {"exact", "paraphrase", "complex"}
    missing_types = non_irrelevant_types - set(type_counts.keys())
    if missing_types:
        errors.append(f"缺少必需类型: {missing_types}")

    # 3. 按类别统计
    cat_counts = Counter(item.get("category", "missing") for item in data)
    print(f"\n类别分布 ({len(cat_counts)} 个类别):")
    for c, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
        marker = "" if n >= MIN_PER_CATEGORY else f" [不足 {MIN_PER_CATEGORY}]"
        print(f"  {c}: {n}{marker}")

    if len(cat_counts) < MIN_CATEGORIES:
        errors.append(f"类别数不足: {len(cat_counts)} < {MIN_CATEGORIES}")

    for c, n in cat_counts.items():
        if n < MIN_PER_CATEGORY:
            warnings.append(f"类别 '{c}' 数量不足: {n} < {MIN_PER_CATEGORY}")

    # 4. 检查每条记录的必需字段
    field_errors = 0
    for i, item in enumerate(data):
        for field in REQUIRED_FIELDS:
            if field not in item:
                field_errors += 1
                if field_errors <= 5:  # 只报告前 5 个
                    errors.append(f"第 {i} 条 (id={item.get('id', '?')}) 缺少字段: {field}")

    if field_errors > 5:
        errors.append(f"... 共 {field_errors} 处字段缺失")

    # 5. 检查 ID 唯一性
    ids = [item.get("id", "") for item in data]
    dup_ids = [id_ for id_, count in Counter(ids).items() if count > 1 and id_]
    if dup_ids:
        errors.append(f"重复 ID: {dup_ids[:5]}")

    # 6. 检查 question 和 ground_truth 非空
    empty_q = sum(1 for item in data if not item.get("question", "").strip())
    empty_a = sum(1 for item in data if not item.get("ground_truth", "").strip())
    if empty_q:
        errors.append(f"空问题: {empty_q} 条")
    if empty_a:
        errors.append(f"空答案: {empty_a} 条")

    # 输出结果
    print("\n" + "=" * 40)
    if errors:
        print(f"FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  ERROR: {e}")
    else:
        print("PASSED")

    if warnings:
        print(f"\nWarning ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN: {w}")

    return len(errors) == 0


def main():
    parser = argparse.ArgumentParser(description="评估数据集验证")
    parser.add_argument(
        "--file",
        default=str(Path(__file__).resolve().parent / "eval_dataset.json"),
        help="数据集文件路径（默认: eval_dataset.json）",
    )
    args = parser.parse_args()

    passed = validate_dataset(args.file)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
