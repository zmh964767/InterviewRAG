"""网页面试题爬虫

支持从掘金、CSDN 等平台抓取面试文章，提取结构化题目。
"""

import hashlib
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from app.models.schemas import Question

logger = logging.getLogger(__name__)

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# 题目识别模式
QUESTION_PATTERNS = [
    re.compile(r"^[\d]+[.、]\s*(.+)"),  # 1. xxx 或 1、xxx
    re.compile(r"^Q[\d]*[：:]\s*(.+)"),  # Q1: xxx
    re.compile(r"^问题[\d]*[：:]\s*(.+)"),  # 问题1: xxx
    re.compile(r"^(什么是|请解释|请介绍|如何|为什么|谈谈).+?[？?]?$"),  # 问答句式
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


def scrape_juejin_article(url: str, category: str = "面试") -> list[Question]:
    """抓取掘金文章"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"请求失败 {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 掘金文章内容
    article = soup.find("article") or soup.find(class_="article-content")
    if not article:
        logger.warning(f"未找到文章内容: {url}")
        return []

    questions: list[Question] = []
    current_answer_lines: list[str] = []
    current_question = ""

    for elem in article.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = elem.get_text(strip=True)
        if not text:
            continue

        if is_question(text):
            # 保存上一题
            if current_question and current_answer_lines:
                q_text = extract_question_text(current_question)
                a_text = "\n".join(current_answer_lines).strip()
                if q_text and a_text:
                    questions.append(
                        Question(
                            id=hashlib.md5(f"{q_text}|{a_text}".encode()).hexdigest()[:12],
                            question=q_text,
                            answer=a_text,
                            category=category,
                            difficulty="中等",
                            source=url,
                            tags=[category],
                        )
                    )

            current_question = text
            current_answer_lines = []
        else:
            if current_question:
                current_answer_lines.append(text)

    # 保存最后一题
    if current_question and current_answer_lines:
        q_text = extract_question_text(current_question)
        a_text = "\n".join(current_answer_lines).strip()
        if q_text and a_text:
            questions.append(
                Question(
                    id=hashlib.md5(f"{q_text}|{a_text}".encode()).hexdigest()[:12],
                    question=q_text,
                    answer=a_text,
                    category=category,
                    difficulty="中等",
                    source=url,
                    tags=[category],
                )
            )

    logger.info(f"从 {url} 抓取 {len(questions)} 道题目")
    return questions


def scrape_generic_page(url: str, category: str = "面试") -> list[Question]:
    """通用网页抓取"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"请求失败 {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 移除脚本和样式
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    questions: list[Question] = []
    current_question = ""
    current_answer_lines: list[str] = []

    for line in lines:
        if is_question(line):
            if current_question and current_answer_lines:
                q_text = extract_question_text(current_question)
                a_text = "\n".join(current_answer_lines).strip()
                if q_text and a_text:
                    questions.append(
                        Question(
                            id=hashlib.md5(f"{q_text}|{a_text}".encode()).hexdigest()[:12],
                            question=q_text,
                            answer=a_text,
                            category=category,
                            difficulty="中等",
                            source=url,
                            tags=[category],
                        )
                    )

            current_question = line
            current_answer_lines = []
        elif current_question:
            current_answer_lines.append(line)

    # 保存最后一题
    if current_question and current_answer_lines:
        q_text = extract_question_text(current_question)
        a_text = "\n".join(current_answer_lines).strip()
        if q_text and a_text:
            questions.append(
                Question(
                    id=hashlib.md5(f"{q_text}|{a_text}".encode()).hexdigest()[:12],
                    question=q_text,
                    answer=a_text,
                    category=category,
                    difficulty="中等",
                    source=url,
                    tags=[category],
                )
            )

    logger.info(f"从 {url} 抓取 {len(questions)} 道题目")
    return questions


def scrape_url(url: str, category: str = "面试") -> list[Question]:
    """根据 URL 自动选择抓取策略"""
    if "juejin.cn" in url:
        return scrape_juejin_article(url, category)
    else:
        return scrape_generic_page(url, category)
