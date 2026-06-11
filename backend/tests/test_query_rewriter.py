"""QueryRewriter 单测

覆盖：正常改写/异常回退/空回退/超时回退/解析边界（少行/多行/前缀编号）。
"""

import asyncio
import time

import pytest
from unittest.mock import Mock, patch

from app.retrievers.query_rewriter import QueryRewriter
from app.services.llm_service import LLMService


@pytest.fixture
def mock_llm():
    """Mock LLMService.chat()"""
    m = Mock(spec=LLMService)
    return m


@pytest.fixture
def rewriter(mock_llm):
    """带 mock LLM 的 QueryRewriter，N=3"""
    return QueryRewriter(llm=mock_llm, n=3, timeout_s=5.0)


def test_rewrite_returns_n_variants(rewriter, mock_llm):
    """正常改写：返回 [原 query, 2 个变体]（N=3）"""
    mock_llm.chat.return_value = "变体一\n变体二"
    result = rewriter.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手", "变体一", "变体二"]
    mock_llm.chat.assert_called_once()


def test_rewrite_returns_fewer_than_n(rewriter, mock_llm):
    """改写返回少于 N-1 个变体：正常截断，不报错"""
    mock_llm.chat.return_value = "变体一"
    result = rewriter.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手", "变体一"]


def test_rewrite_with_prefixes(rewriter, mock_llm):
    """改写返回带编号/前缀的行：自动去除前缀"""
    mock_llm.chat.return_value = "1. 变体一\n2. 变体二\n3. 变体三"
    result = rewriter.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手", "变体一", "变体二", "变体三"]


def test_rewrite_with_bullet_prefixes(rewriter, mock_llm):
    """改写返回 bullet 点符号：自动去除"""
    mock_llm.chat.return_value = "- 变体一\n* 变体二\n• 变体三"
    result = rewriter.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手", "变体一", "变体二", "变体三"]


def test_rewrite_with_extra_blank_lines(rewriter, mock_llm):
    """改写返回空行：自动过滤"""
    mock_llm.chat.return_value = "变体一\n\n\n变体二\n  \n"
    result = rewriter.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手", "变体一", "变体二"]


def test_rewrite_empty_response_fallback(rewriter, mock_llm):
    """改写返回空/空串：回退 [原 query]"""
    mock_llm.chat.return_value = ""
    result = rewriter.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手"]


def test_rewrite_llm_error_fallback(rewriter, mock_llm):
    """LLM 抛异常：回退 [原 query]，不向上抛"""
    mock_llm.chat.side_effect = Exception("智谱 API 挂了")
    result = rewriter.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手"]


def test_rewrite_timeout_fallback(rewriter, mock_llm):
    """改写超时：回退 [原 query]"""
    async def slow_chat(*args, **kwargs):
        await asyncio.sleep(10)
        return "变体一"

    mock_llm.chat = Mock(side_effect=lambda *a, **k: asyncio.run(slow_chat(*a, **k)))
    # N=3, timeout=5s
    fast_rewriter = QueryRewriter(llm=mock_llm, n=3, timeout_s=0.1)
    start = time.time()
    result = fast_rewriter.rewrite("TCP 三次握手")
    elapsed = time.time() - start
    assert result == ["TCP 三次握手"]
    assert elapsed < 1.0  # 超时生效


def test_rewrite_n_equals_1(rewriter, mock_llm):
    """N=1 时只返回原 query（改写层不跑）"""
    mock_llm.chat.return_value = "变体一"
    rewriter_n1 = QueryRewriter(llm=mock_llm, n=1, timeout_s=5.0)
    result = rewriter_n1.rewrite("TCP 三次握手")
    assert result == ["TCP 三次握手"]
    mock_llm.chat.assert_not_called()


def test_arewrite_is_async_entry(rewriter, mock_llm):
    """arewrite 异步入口：与 rewrite 行为一致"""
    mock_llm.chat.return_value = "变体一\n变体二"
    result = asyncio.run(rewriter.arewrite("TCP 三次握手"))
    assert result == ["TCP 三次握手", "变体一", "变体二"]
    mock_llm.chat.assert_called_once()


# =========================================================================
# prompt_variant 测试
# =========================================================================


def test_variant_1_uses_default_temperature(mock_llm):
    """variant=1: 温度 0.3"""
    mock_llm.chat.return_value = "变体一"
    rw = QueryRewriter(mock_llm, n=3, timeout_s=5.0, prompt_variant=1)
    rw.rewrite("Q")
    call_args = mock_llm.chat.call_args
    assert call_args.kwargs.get("temperature", call_args[1].get("temperature", None)) == 0.3


def test_variant_4_uses_high_temperature(mock_llm):
    """variant=4: 温度 0.7（鼓励多样性）"""
    mock_llm.chat.return_value = "变体一"
    rw = QueryRewriter(mock_llm, n=3, timeout_s=5.0, prompt_variant=4)
    rw.rewrite("Q")
    call_args = mock_llm.chat.call_args
    assert call_args.kwargs.get("temperature", call_args[1].get("temperature", None)) == 0.7


def test_variant_5_uses_moderate_temperature(mock_llm):
    """variant=5: 温度 0.5"""
    mock_llm.chat.return_value = "变体一"
    rw = QueryRewriter(mock_llm, n=3, timeout_s=5.0, prompt_variant=5)
    rw.rewrite("Q")
    call_args = mock_llm.chat.call_args
    assert call_args.kwargs.get("temperature", call_args[1].get("temperature", None)) == 0.5


def test_variant_unknown_falls_back_to_v1(mock_llm):
    """未知 variant：回退 v1，不报错"""
    mock_llm.chat.return_value = "变体一"
    rw = QueryRewriter(mock_llm, n=3, timeout_s=5.0, prompt_variant=99)
    result = rw.rewrite("Q")
    assert rw.prompt_variant == 1
    assert result[0] == "Q"


def test_variant_2_prompt_includes_technical_terms(mock_llm):
    """variant=2 prompt 包含技术术语保留约束"""
    mock_llm.chat.return_value = "变体一"
    rw = QueryRewriter(mock_llm, n=3, timeout_s=5.0, prompt_variant=2)
    assert "技术术语" in rw.prompt_template or "技术名称" in rw.prompt_template or "技术" in rw.prompt_template


def test_variant_3_prompt_includes_examples(mock_llm):
    """variant=3 few-shot prompt 包含示例"""
    mock_llm.chat.return_value = "变体一"
    rw = QueryRewriter(mock_llm, n=3, timeout_s=5.0, prompt_variant=3)
    assert "TCP" in rw.prompt_template  # few-shot 里有 TCP 三次握手示例


def test_variant_prompt_file_all_exist():
    """5 个 variant 的 prompt 文件都存在"""
    from app.retrievers.query_rewriter import _PROMPTS_DIR, _PROMPT_FILES
    for v, filename in _PROMPT_FILES.items():
        path = _PROMPTS_DIR / filename
        assert path.exists(), f"variant {v} prompt file missing: {path}"