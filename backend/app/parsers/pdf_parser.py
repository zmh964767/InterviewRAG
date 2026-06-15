"""PDF 面试题解析器"""

import io
import logging
import re
from pathlib import Path

from pypdf import PdfReader

from app.models.schemas import Question
from app.parsers.common import build_question, extract_question_text, is_question

logger = logging.getLogger(__name__)

CHAPTER_PATTERNS = [
    re.compile(r"^(?:第[一二三四五六七八九十\d]+章|Chapter\s+\d+|Part\s+\d+)[：:\s]*(.+)"),
    re.compile(r"^(?:第[一二三四五六七八九十\d]+节|Section\s+\d+)[：:\s]*(.+)"),
]


def _infer_category_from_filename(filename: str) -> str:
    """从文件名推断分类"""
    name = Path(filename).stem
    name = re.sub(r"^(?:第?\d+[-_、]|Extra\d+[-_、]|\d+[-_、])", "", name)
    return name.strip() or "PDF面试题"


def parse_pdf(file_path: str, category: str | None = None) -> list[Question]:
    """解析 PDF 文件"""
    if category is None:
        category = _infer_category_from_filename(file_path)

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


def parse_pdf_content(content: bytes, filename: str, category: str | None = None) -> list[Question]:
    """解析 PDF 内容（字节流）"""
    if category is None:
        category = _infer_category_from_filename(filename)

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
    current_category = category

    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        for pattern in CHAPTER_PATTERNS:
            m = pattern.match(line)
            if m:
                current_category = m.group(1).strip() or m.group(0).strip()
                break

        if is_question(line):
            # 保存上一题
            if current_question and current_answer_lines:
                q = build_question(
                    extract_question_text(current_question),
                    "\n".join(current_answer_lines),
                    current_category,
                    source,
                )
                if q:
                    questions.append(q)

            current_question = line
            current_answer_lines = []
        elif current_question:
            current_answer_lines.append(line)

    # 保存最后一题
    if current_question and current_answer_lines:
        q = build_question(
            extract_question_text(current_question),
            "\n".join(current_answer_lines),
            current_category,
            source,
        )
        if q:
            questions.append(q)

    logger.info(f"从 PDF 解析 {len(questions)} 道题目")
    return questions
