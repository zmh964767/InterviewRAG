"""检索质量指标

Hit Rate@K 和 MRR 的纯函数实现。

使用关键词重叠匹配（适合中文改写场景）：
- 提取 eval_question 中的关键名词/术语（至少 2 字符）
- 检查这些关键词是否出现在检索结果的题目部分
- 匹配率 > 0.6 视为命中

这种方法比 SequenceMatcher 更适合中文改写（不同措辞，相同关键词）。
"""

import re


def _extract_keywords(text: str) -> set[str]:
    """从中文文本中提取关键词（2-4 字符的中文词 + 英文单词）

    使用滑动窗口 + 常见停用词过滤，提取有意义的短词。
    """
    # 提取英文单词（至少 2 字符）
    en_words = set(re.findall(r'[A-Za-z]{2,}', text))

    # 提取中文：先去标点，再用 2-4 字符滑动窗口
    cn_text = re.sub(r'[，。？！、；：""''（）【】《》\s]+', ' ', text)
    cn_segments = cn_text.split()

    cn_words = set()
    for seg in cn_segments:
        # 提取纯中文部分
        cn_parts = re.findall(r'[一-鿿]+', seg)
        for part in cn_parts:
            # 2-4 字符滑动窗口
            for size in range(2, min(5, len(part) + 1)):
                for i in range(len(part) - size + 1):
                    word = part[i:i + size]
                    # 过滤常见停用词
                    if word not in {'的', '了', '是', '在', '和', '与', '或', '等', '有', '对', '被', '把', '将', '从', '到', '也', '都', '就', '才', '只', '但', '而', '如果', '因为', '所以', '可以', '这个', '那个', '什么', '怎么', '如何', '为什么', '哪些', '哪个', '一个', '一种', '一些', '通过', '进行', '使用', '能够', '需要', '应该', '已经', '正在', '以及', '或者', '并且', '而且', '但是', '然而', '因此', '所以', '如果', '那么', '这样', '那样', '这里', '那里', '其中', '之间', '之后', '之前', '以上', '以下', '关于', '对于', '来说', '而言', '的话', '时候', '地方', '东西', '问题', '情况', '方面', '部分', '整个', '所有', '任何', '每个', '某个', '这些', '那些', '哪些', '什么', '怎么', '如何', '为什么', '哪里', '哪个', '哪些'}:
                        cn_words.add(word)

    return cn_words | en_words


def question_match(retrieved_text: str, eval_question: str, threshold: float = 0.6) -> bool:
    """判断检索结果是否匹配评估题目（关键词重叠 + 子串匹配）

    Args:
        retrieved_text: ChromaDB 返回的文档文本（"题目：xxx\n答案：yyy"）
        eval_question: eval_dataset 的 question 字段
        threshold: 匹配率阈值（0-1），默认 0.6

    Returns:
        True if 关键词匹配率 > threshold
    """
    # 从 ChromaDB 文档中提取题目部分
    if "题目：" in retrieved_text:
        q_part = retrieved_text.split("题目：")[1].split("\n")[0].strip()
    elif "题目:" in retrieved_text:
        q_part = retrieved_text.split("题目:")[1].split("\n")[0].strip()
    else:
        q_part = retrieved_text[:200]

    # 提取关键词
    eval_kws = _extract_keywords(eval_question)
    doc_kws = _extract_keywords(q_part)

    if not eval_kws:
        return False

    # 计算匹配数：精确匹配 + 子串匹配
    matched = 0
    for ek in eval_kws:
        # 精确匹配
        if ek in doc_kws:
            matched += 1
            continue
        # 子串匹配（eval 关键词是 doc 关键词的子串，或反过来）
        for dk in doc_kws:
            if len(ek) >= 2 and len(dk) >= 2 and (ek in dk or dk in ek):
                matched += 1
                break

    ratio = matched / len(eval_kws)
    return ratio >= threshold


def hit_rate_at_k(retrieved_texts: list[str], eval_question: str, k: int = 5) -> bool:
    """top-k 检索结果中是否包含与评估题目匹配的文档

    Args:
        retrieved_texts: top-k 文档文本列表（ChromaDB 原文）
        eval_question: eval_dataset 的 question 字段
        k: 截断数

    Returns:
        True if top-k 中有关键词匹配率 > 0.6 的结果
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

