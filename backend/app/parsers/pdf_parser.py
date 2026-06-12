"""PDF 面试题解析器"""

import hashlib
import logging
import re

from app.models.schemas import Question

logger = logging.getLogger(__name__)

# 题目识别模式
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
    """提取题目文本"""
    text = text.strip()
    for pattern in QUESTION_PATTERNS:
        match = pattern.match(text)
        if match and match.lastindex:
            return match.group(1).strip()
    return text


def parse_pdf(file_path: str, category: str = "PDF面试题") -> list[Question]:
    """解析 PDF 文件"""
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader

    try:
        reader = PdfReader(file_path)
    except Exception as e:
        logger.error(f"读取 PDF 失败: {e}")
        return []

    # 提取所有文本
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

    if not full_text.strip():
        logger.warning(f"PDF 无文本内容: {file_path}")
        return []

    return parse_text_content(full_text, file_path, category)


def parse_pdf_content(content: bytes, filename: str, category: str = "PDF面试题") -> list[Question]:
    """解析 PDF 内容（字节流）"""
    try:
        from pypdf import PdfReader
        import io
    except ImportError:
        from PyPDF2 import PdfReader
        import io

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as e:
        logger.error(f"解析 PDF 失败: {e}")
        return []

    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

    if not full_text.strip():
        logger.warning(f"PDF 无文本内容: {filename}")
        return []

    return parse_text_content(full_text, filename, category)


def parse_text_content(text: str, source: str, category: str) -> list[Question]:
    """从文本内容解析题目"""
    questions: list[Question] = []
    current_question = ""
    current_answer_lines: list[str] = []

    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if is_question(line):
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
                            source=source,
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
                    source=source,
                    tags=[category],
                )
            )

    logger.info(f"从 PDF 解析 {len(questions)} 道题目")
    return questions
