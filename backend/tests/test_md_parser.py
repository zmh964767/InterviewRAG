"""MD 解析器测试"""

import pytest
from app.parsers.md_parser import parse_md_content, clean_html, generate_id


@pytest.fixture
def sample_md_content():
    return """### <strong>1. LLM 八股</strong>

#### <strong>1.1 什么是Transformer？</strong>

* <strong>参考答案：</strong>
    Transformer是一种基于自注意力机制的模型架构。

---

#### <strong>1.2 什么是位置编码？</strong>

* <strong>参考答案：</strong>
    位置编码是向模型注入位置信息的向量。
"""


class TestParseMdContent:
    """parse_md_content 函数"""

    def test_returns_list(self, sample_md_content):
        result = parse_md_content(sample_md_content)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_extracts_question(self, sample_md_content):
        result = parse_md_content(sample_md_content)
        assert "什么是Transformer" in result[0].question

    def test_extracts_answer(self, sample_md_content):
        result = parse_md_content(sample_md_content)
        assert "自注意力机制" in result[0].answer

    def test_extracts_category(self, sample_md_content):
        result = parse_md_content(sample_md_content)
        assert "LLM" in result[0].category

    def test_generates_id(self, sample_md_content):
        result = parse_md_content(sample_md_content)
        assert result[0].id is not None
        assert len(result[0].id) > 0

    def test_handles_empty_content(self):
        result = parse_md_content("")
        assert result == []

    def test_handles_no_answers(self):
        md = "#### <strong>1.1 问题</strong>\n\n一些内容但没有参考答案标记"
        result = parse_md_content(md)
        assert isinstance(result, list)

    def test_multiple_categories(self):
        md = """### <strong>1. LLM</strong>

#### <strong>1.1 问题1</strong>

* <strong>参考答案：</strong>答案1

---

### <strong>2. VLM</strong>

#### <strong>2.1 问题2</strong>

* <strong>参考答案：</strong>答案2
"""
        result = parse_md_content(md)
        assert len(result) == 2
        categories = [r.category for r in result]
        assert any("LLM" in c for c in categories)
        assert any("VLM" in c for c in categories)


class TestFallbackRegex:
    """无 <strong> 标签的 fallback 正则"""

    def test_plain_chapter_and_question(self):
        md = """### 1. LLM 基础

#### 1.1 什么是 Transformer？

* 参考答案：Transformer 是一种模型架构。

---

#### 1.2 什么是位置编码？

* 参考答案：位置编码用于注入位置信息。
"""
        result = parse_md_content(md)
        assert len(result) == 2
        assert "Transformer" in result[0].question
        assert result[0].answer  # 非空

    def test_plain_answer_marker(self):
        md = """### 1. 测试

#### 1.1 第一题？

* 参考答案：这是答案。
"""
        result = parse_md_content(md)
        assert len(result) == 1
        assert "这是答案" in result[0].answer

    def test_no_match_warning(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            parse_md_content("some random text without any structure")
        assert any("未匹配到任何题目" in r.message for r in caplog.records)


class TestCleanHtml:
    """clean_html 函数"""

    def test_removes_strong_tags(self):
        assert clean_html("<strong>hello</strong>") == "hello"

    def test_removes_multiple_tags(self):
        result = clean_html("<strong>a</strong> and <strong>b</strong>")
        assert result == "a and b"

    def test_handles_no_tags(self):
        assert clean_html("plain text") == "plain text"


class TestGenerateId:
    """generate_id 函数"""

    def test_generates_deterministic_id(self):
        id1 = generate_id("1", "1.1")
        id2 = generate_id("1", "1.1")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = generate_id("1", "1.1")
        id2 = generate_id("1", "1.2")
        assert id1 != id2
