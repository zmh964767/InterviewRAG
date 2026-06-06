"""Markdown 面试题解析器

解析格式：
### <strong>1. 章节标题</strong>
#### <strong>1.1 题目内容</strong>
* <strong>参考答案：</strong>
    答案内容...
"""

import re
import hashlib
import logging
from pathlib import Path

from app.models.schemas import Question

logger = logging.getLogger(__name__)

# 章节标题正则（只匹配 ### 不匹配 ####）
CHAPTER_PATTERN = re.compile(
    r"^###\s+<strong>\s*(\d+)\.\s*(.+?)\s*</strong>",
    re.IGNORECASE,
)

# 题目标题正则（只匹配 #### 不匹配 #####）
QUESTION_PATTERN = re.compile(
    r"^####\s+<strong>\s*(\d+\.\d+)\s*(.+?)\s*</strong>",
    re.IGNORECASE,
)

# 答案标记
ANSWER_MARKER = re.compile(
    r"\*\s*<strong>\s*参考答案[：:]\s*</strong>",
    re.IGNORECASE,
)

# HTML 标签清理
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
# LaTeX 公式清理
LATEX_PATTERN = re.compile(r"\$[^$]+\$|\\[a-zA-Z]+")
# 多余空白
MULTI_SPACE = re.compile(r"\s+")
MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_html(text: str) -> str:
    """清理 HTML 标签"""
    text = HTML_TAG_PATTERN.sub("", text)
    text = LATEX_PATTERN.sub("[公式]", text)
    text = MULTI_SPACE.sub(" ", text)
    text = MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def generate_id(chapter: str, question_num: str) -> str:
    """生成唯一 ID"""
    content = f"{chapter}|{question_num}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def parse_md_file(file_path: str) -> list[Question]:
    """解析 MD 文件，返回题目列表"""
    path = Path(file_path)
    if not path.exists():
        logger.error(f"文件不存在: {file_path}")
        return []

    content = path.read_text(encoding="utf-8")
    return parse_md_content(content, source=path.name)


def parse_md_content(content: str, source: str = "unknown") -> list[Question]:
    """解析 MD 内容"""
    questions: list[Question] = []
    current_chapter = ""
    current_chapter_name = ""

    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 匹配章节
        chapter_match = CHAPTER_PATTERN.search(line)
        if chapter_match:
            current_chapter = chapter_match.group(1)
            current_chapter_name = clean_html(chapter_match.group(2))
            i += 1
            continue

        # 匹配题目
        question_match = QUESTION_PATTERN.search(line)
        if question_match:
            question_num = question_match.group(1)
            question_text = clean_html(question_match.group(2))

            # 向下找答案
            answer_lines = []
            in_answer = False
            i += 1

            while i < len(lines):
                next_line = lines[i].strip()

                # 遇到下一题目或章节，停止
                if QUESTION_PATTERN.search(next_line) or CHAPTER_PATTERN.search(next_line):
                    break

                # 遇到分隔线，停止
                if next_line == "---":
                    i += 1
                    break

                # 检测答案标记
                if ANSWER_MARKER.search(next_line):
                    in_answer = True
                    # 答案标记后的同一行内容
                    after_marker = ANSWER_MARKER.sub("", next_line).strip()
                    if after_marker:
                        answer_lines.append(after_marker)
                    i += 1
                    continue

                if in_answer:
                    # 排除空行在答案开头
                    if not next_line and not answer_lines:
                        i += 1
                        continue
                    answer_lines.append(next_line)

                i += 1

            answer_text = clean_html("\n".join(answer_lines).strip())

            if question_text and answer_text:
                q = Question(
                    id=generate_id(current_chapter, question_num),
                    question=question_text,
                    answer=answer_text,
                    category=current_chapter_name or "未分类",
                    difficulty="中等",
                    source=source,
                    tags=[current_chapter_name] if current_chapter_name else [],
                )
                questions.append(q)
                logger.debug(f"解析题目: {question_num} {question_text[:50]}...")
            else:
                logger.warning(f"题目 {question_num} 答案为空，跳过")

            continue

        i += 1

    logger.info(f"共解析 {len(questions)} 道题目")
    return questions


def save_to_json(questions: list[Question], output_path: str):
    """保存为 JSON 文件"""
    import json

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [q.model_dump(mode="json") for q in questions]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"已保存 {len(questions)} 道题目到 {output_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法: python -m app.parsers.md_parser <input.md> <output.json>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    questions = parse_md_file(input_file)
    save_to_json(questions, output_file)
    print(f"解析完成: {len(questions)} 道题目")
