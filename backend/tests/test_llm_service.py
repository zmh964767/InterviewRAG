"""LLMService 单测（Facade 层）

测试委托逻辑和 sync→async stream 适配。
Provider 实现本身的测试见 test_providers.py。
"""

import pytest
from unittest.mock import MagicMock

from app.services.llm_service import LLMService
from app.providers import LLMProvider


def _make_mock_provider():
    """创建 mock LLMProvider"""
    provider = MagicMock(spec=LLMProvider)
    provider.chat.return_value = "mock answer"
    provider.chat_stream.return_value = iter(["mock ", "answer"])
    provider.check_health.return_value = "ok"
    # 默认无 token 用量（避免 MagicMock 值被传给 prometheus observe）
    provider.last_usage = None
    return provider


@pytest.fixture
def llm_service():
    provider = _make_mock_provider()
    return LLMService(provider=provider)


def test_chat_happy(llm_service):
    """chat 委托给 provider 并返回结果"""
    result = llm_service.chat([{"role": "user", "content": "你好"}])
    assert result == "mock answer"
    llm_service.provider.chat.assert_called_once()


def test_chat_passes_kwargs(llm_service):
    """temperature / max_tokens 透传给 provider"""
    llm_service.chat([{"role": "user", "content": "hi"}], temperature=0.5, max_tokens=100)
    llm_service.provider.chat.assert_called_with(
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.5,
        max_tokens=100,
    )


@pytest.mark.asyncio
async def test_chat_stream_happy(llm_service):
    """chat_stream 将 sync generator 转 async generator"""
    tokens = []
    async for token in llm_service.chat_stream([{"role": "user", "content": "你好"}]):
        tokens.append(token)
    assert tokens == ["mock ", "answer"]


def test_check_health(llm_service):
    """check_health 委托给 provider"""
    assert llm_service.check_health() == "ok"
    llm_service.provider.check_health.assert_called_once()


def test_default_provider():
    """不传 provider 时自动创建默认 Provider"""
    service = LLMService()
    assert service.provider is not None
    assert isinstance(service.provider, LLMProvider)
