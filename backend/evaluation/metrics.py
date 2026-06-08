"""检索质量指标

Hit Rate@K 和 MRR 的纯函数实现。

注意：由于 eval_dataset.json 的 id（如 recall_001）与 ChromaDB 存储的
id（如 31bf48162aa4）不一致，Hit Rate 用**文本内容匹配**（question 相似度 > 0.8），
不是 id 精确匹配。
"""

from difflib import SequenceMatcher


def question_match(retrieved_text: str, eval_question: str, threshold: float = 0.7) -> bool:
    """判断检索结果是否匹配评估题目（文本相似度）

    Args:
        retrieved_text: ChromaDB 返回的文档文本（"题目：xxx\n答案：yyy"）
        eval_question: eval_dataset 的 question 字段
        threshold: 相似度阈值（0-1），默认 0.7

    Returns:
        True if 相似度 > threshold
    """
    # 从 ChromaDB 文档中提取题目部分
    if "题目：" in retrieved_text:
        q_part = retrieved_text.split("题目：")[1].split("\n")[0].strip()
    elif "题目:" in retrieved_text:
        q_part = retrieved_text.split("题目:")[1].split("\n")[0].strip()
    else:
        q_part = retrieved_text[:200]

    # 用 SequenceMatcher 计算相似度（中文友好）
    ratio = SequenceMatcher(None, eval_question.strip(), q_part.strip()).ratio()
    return ratio > threshold


def hit_rate_at_k(retrieved_texts: list[str], eval_question: str, k: int = 5) -> bool:
    """top-k 检索结果中是否包含与评估题目匹配的文档

    Args:
        retrieved_texts: top-k 文档文本列表（ChromaDB 原文）
        eval_question: eval_dataset 的 question 字段
        k: 截断数

    Returns:
        True if top-k 中有文本相似度 > 0.7 的结果
    """
    for text in retrieved_texts[:k]:
        if question_match(text, eval_question):
            return True
    return False


def mrr(retrieved_texts: list[str], eval_question: str) -> float:
    """Mean Reciprocal Rank（单题版）

    第一个匹配文档的排名的倒数。
    """
    for rank, text in enumerate(retrieved_texts, 1):
        if question_match(text, eval_question):
            return 1.0 / rank
    return 0.0


def compute_retrieval_metrics(
    results: list[dict],
    k: int = 5,
) -> dict:
    """批量计算检索指标

    Args:
        results: [{"retrieved_texts": [...], "eval_question": "..."}, ...]
        k: Hit Rate 截断数

    Returns:
        {"hit_rate@k": float, "mrr": float}
    """
    if not results:
        return {f"hit_rate@{k}": 0.0, "mrr": 0.0}

    hr_sum = 0
    mrr_sum = 0.0
    for r in results:
        retrieved = r.get("retrieved_texts", [])
        question = r.get("eval_question", "")
        if not question:
            continue
        if hit_rate_at_k(retrieved, question, k):
            hr_sum += 1
        mrr_sum += mrr(retrieved, question)

    n = len(results)
    return {
        f"hit_rate@{k}": hr_sum / n,
        "mrr": mrr_sum / n,
    }

