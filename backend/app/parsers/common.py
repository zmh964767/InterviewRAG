"""Parser 共享模块

消除 pdf_parser / web_scraper 的重复代码:
- QUESTION_PATTERNS: 题目识别正则
- is_question(): 判断文本是否是题目
- extract_question_text(): 提取题目文本（去掉编号）
- build_question(): 统一构建 Question 对象
"""

import hashlib
import logging
import re

from app.models.schemas import Question

logger = logging.getLogger(__name__)

# =====================================================================
# 题目识别模式
# =====================================================================

QUESTION_PATTERNS = [
    re.compile(r"^[\d]+[.、]\s*(.+)"),
    re.compile(r"^Q[\d]*[：:]\s*(.+)"),
    re.compile(r"^问题[\d]*[：:]\s*(.+)"),
    re.compile(r"^(什么是|请解释|请介绍|如何|为什么|谈谈).+?[？?]?$"),
]


def is_question(text: str) -> bool:
    """判断文本是否是题目"""
    text = text.strip()
    if len(text) < 10 or len(text) > 200:
        return False
    for pattern in QUESTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def extract_question_text(text: str) -> str:
    """提取题目文本（去掉编号等）"""
    text = text.strip()
    for pattern in QUESTION_PATTERNS:
        match = pattern.match(text)
        if match and match.lastindex:
            return match.group(1).strip()
    return text


def build_question(
    q_text: str,
    a_text: str,
    category: str,
    source: str,
) -> Question | None:
    """统一构建 Question 对象。

    无效输入（空文本）返回 None。
    ID 由 md5(q_text|a_text) 前 16 位生成。
    """
    if not q_text or not a_text:
        return None
    q_text = q_text.strip()
    a_text = a_text.strip()
    if not q_text or not a_text:
        return None
    qid = hashlib.md5(f"{q_text}|{a_text}".encode()).hexdigest()[:16]
    return Question(
        id=qid,
        question=q_text,
        answer=a_text,
        category=category,
        difficulty="中等",
        source=source,
        tags=[category],
    )
