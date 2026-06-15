"""Parser 共享模块测试"""

import pytest

from app.parsers.common import build_question, extract_question_text, is_question


class TestIsQuestion:
    """is_question 函数"""

    def test_numbered_question(self):
        assert is_question("1. 什么是 Transformer？")

    def test_q_prefix(self):
        assert is_question("Q1：请解释注意力机制")

    def test_question_prefix(self):
        assert is_question("问题1：什么是 BERT？")

    def test_wh_question(self):
        assert is_question("什么是 Transformer 的自注意力机制？")

    def test_how_question(self):
        assert is_question("如何优化模型的推理速度？")

    def test_too_short(self):
        assert not is_question("太短")

    def test_too_long(self):
        assert not is_question("x" * 201)

    def test_normal_text(self):
        assert not is_question("这是一段普通的描述性文本，不是问题")


class TestExtractQuestionText:
    """extract_question_text 函数"""

    def test_numbered(self):
        assert extract_question_text("1. 什么是 Transformer？") == "什么是 Transformer？"

    def test_q_prefix(self):
        assert extract_question_text("Q1：请解释注意力机制") == "请解释注意力机制"

    def test_no_pattern(self):
        text = "描述一下 Transformer 的整体架构设计"
        assert extract_question_text(text) == text


class TestBuildQuestion:
    """build_question 函数"""

    def test_builds_question(self):
        q = build_question("什么是X？", "X是一种技术", "面试", "test.md")
        assert q is not None
        assert q.question == "什么是X？"
        assert q.answer == "X是一种技术"
        assert q.category == "面试"
        assert q.source == "test.md"
        assert q.difficulty == "中等"
        assert q.tags == ["面试"]

    def test_id_is_16_chars(self):
        q = build_question("q", "a", "cat", "src")
        assert q is not None
        assert len(q.id) == 16

    def test_deterministic_id(self):
        q1 = build_question("q", "a", "cat", "src")
        q2 = build_question("q", "a", "cat", "src")
        assert q1 is not None and q2 is not None
        assert q1.id == q2.id

    def test_different_content_different_id(self):
        q1 = build_question("q1", "a", "cat", "src")
        q2 = build_question("q2", "a", "cat", "src")
        assert q1 is not None and q2 is not None
        assert q1.id != q2.id

    def test_empty_question_returns_none(self):
        assert build_question("", "answer", "cat", "src") is None

    def test_empty_answer_returns_none(self):
        assert build_question("question", "", "cat", "src") is None

    def test_none_inputs_returns_none(self):
        assert build_question(None, "a", "cat", "src") is None  # type: ignore[arg-type]

    def test_whitespace_only_returns_none(self):
        assert build_question("   ", "  ", "cat", "src") is None
