"""检索质量指标

Hit Rate@K 和 MRR 的纯函数实现。
"""


def hit_rate_at_k(retrieved_ids: list[str], relevant_id: str, k: int = 5) -> bool:
    """top-k 中是否包含相关文档

    Args:
        retrieved_ids: 检索结果 id 列表（按相关度排序）
        relevant_id: ground_truth 对应的题目 id
        k: 截断数

    Returns:
        True if relevant_id in retrieved_ids[:k]
    """
    return relevant_id in retrieved_ids[:k]


def mrr(retrieved_ids: list[str], relevant_id: str) -> float:
    """Mean Reciprocal Rank（单题版）

    如果相关文档排第 1 → 1.0
    排第 2 → 0.5
    排第 3 → 1/3 ≈ 0.33
    不在结果中 → 0.0
    """
    try:
        rank = retrieved_ids.index(relevant_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0


def compute_retrieval_metrics(
    results: list[dict],
    k: int = 5,
) -> dict:
    """批量计算检索指标

    Args:
        results: [{"retrieved_ids": [...], "relevant_id": "..."}, ...]
        k: Hit Rate 截断数

    Returns:
        {"hit_rate@k": float, "mrr": float}
    """
    if not results:
        return {f"hit_rate@{k}": 0.0, "mrr": 0.0}

    hr_sum = 0
    mrr_sum = 0.0
    for r in results:
        retrieved = r.get("retrieved_ids", [])
        relevant = r.get("relevant_id", "")
        if not relevant:
            continue
        if hit_rate_at_k(retrieved, relevant, k):
            hr_sum += 1
        mrr_sum += mrr(retrieved, relevant)

    n = len(results)
    return {
        f"hit_rate@{k}": hr_sum / n,
        "mrr": mrr_sum / n,
    }
