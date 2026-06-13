"""LLMService 单测"""

import pytest
from unittest.mock import MagicMock

from app.services.llm_service import LLMService
from app.core.exceptions import ExternalServiceError


@pytest.fixture
def llm_service(monkeypatch):
    """构造 LLMService，mock 掉 ZhipuAI client"""
    mock_settings = MagicMock(
        zhipu_api_key="test-key",
        llm_model="glm-4-flash",
        llm_temperature=0.7,
        llm_max_tokens=2048,
    )
    monkeypatch.setattr("app.services.llm_service.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.services.llm_service.ZhipuAI", MagicMock)
    service = LLMService()
    return service


def test_chat_happy(llm_service):
    """happy path: chat 返回文本"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="这是一个回答"))]
    llm_service.client.chat.completions.create = MagicMock(return_value=mock_resp)

    result = llm_service.chat([{"role": "user", "content": "你好"}])
    assert result == "这是一个回答"


@pytest.mark.asyncio
async def test_chat_stream_happy(llm_service):
    """happy path: chat_stream 流式返回多个 chunk"""
    chunks = [
        MagicMock(choices=[MagicMock(delta=MagicMock(content="你"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content="好"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
    ]
    llm_service.client.chat.completions.create = MagicMock(return_value=iter(chunks))

    tokens = []
    async for token in llm_service.chat_stream([{"role": "user", "content": "你好"}]):
        tokens.append(token)
    assert tokens == ["你", "好"]


def test_chat_api_error(llm_service):
    """error path: API 调用失败抛出 ExternalServiceError"""
    llm_service.client.chat.completions.create = MagicMock(side_effect=Exception("API error"))

    with pytest.raises(ExternalServiceError, match="智谱API"):
        llm_service.chat([{"role": "user", "content": "你好"}])
