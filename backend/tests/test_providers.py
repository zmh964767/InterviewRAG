"""LLM / Embedding Provider 单测

测试所有 Provider 实现和工厂函数的正确性。
"""

import pytest
from unittest.mock import MagicMock

import app.providers.factory  # for monkeypatch.setitem on _PROVIDER_MAP

from app.providers import (
    create_llm_provider,
    create_embedding_provider,
    ZhipuLLMProvider,
    ZhipuEmbeddingProvider,
    OpenAIStyleLLMProvider,
    OpenAIStyleEmbeddingProvider,
)
from app.core.exceptions import ExternalServiceError


# =========================================================================
# ZhipuLLMProvider
# =========================================================================


@pytest.fixture
def zhipu_llm(monkeypatch):
    """构造 ZhipuLLMProvider，mock 掉 ZhipuAI client"""
    mock_settings = MagicMock(
        zhipu_api_key="test-key",
        llm_model="glm-4-flash",
        llm_temperature=0.7,
        llm_max_tokens=2048,
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.zhipu.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.providers.zhipu.ZhipuAI", MagicMock)
    provider = ZhipuLLMProvider()
    yield provider


def test_zhipu_llm_requires_key(monkeypatch):
    """缺失 api_key 时抛出 ExternalServiceError"""
    mock_settings = MagicMock(zhipu_api_key="")
    monkeypatch.setattr("app.providers.zhipu.get_settings", lambda: mock_settings)
    with pytest.raises(ExternalServiceError, match="智谱API"):
        ZhipuLLMProvider()


def test_zhipu_llm_chat_happy(zhipu_llm):
    """chat 返回文本"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="你好世界"))]
    zhipu_llm.client.chat.completions.create = MagicMock(return_value=mock_resp)

    result = zhipu_llm.chat([{"role": "user", "content": "你好"}])
    assert result == "你好世界"


def test_zhipu_llm_chat_api_error(zhipu_llm):
    """chat API 异常抛出 ExternalServiceError"""
    zhipu_llm.client.chat.completions.create = MagicMock(side_effect=Exception("API error"))
    with pytest.raises(ExternalServiceError, match="智谱API"):
        zhipu_llm.chat([{"role": "user", "content": "你好"}])


def test_zhipu_llm_chat_stream_happy(zhipu_llm):
    """chat_stream 逐 token 产出"""
    chunks = [
        MagicMock(choices=[MagicMock(delta=MagicMock(content="你"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content="好"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
    ]
    zhipu_llm.client.chat.completions.create = MagicMock(return_value=iter(chunks))

    tokens = list(zhipu_llm.chat_stream([{"role": "user", "content": "你好"}]))
    assert tokens == ["你", "好"]


def test_zhipu_llm_check_health_ok(zhipu_llm):
    """健康检查成功返回 'ok'"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="hi"))]
    zhipu_llm.client.chat.completions.create = MagicMock(return_value=mock_resp)

    assert zhipu_llm.check_health() == "ok"


def test_zhipu_llm_check_health_error(zhipu_llm):
    """健康检查失败返回 'error'"""
    zhipu_llm.client.chat.completions.create = MagicMock(side_effect=Exception("error"))
    assert zhipu_llm.check_health() == "error"


# =========================================================================
# ZhipuEmbeddingProvider
# =========================================================================


@pytest.fixture
def zhipu_embed(monkeypatch):
    """构造 ZhipuEmbeddingProvider，mock 掉 ZhipuAI client"""
    mock_settings = MagicMock(
        zhipu_api_key="test-key",
        embedding_model="embedding-3",
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.zhipu.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.providers.zhipu.ZhipuAI", MagicMock)
    provider = ZhipuEmbeddingProvider()
    yield provider


def test_zhipu_embed_requires_key(monkeypatch):
    """缺失 api_key 时抛出 ExternalServiceError"""
    mock_settings = MagicMock(zhipu_api_key="")
    monkeypatch.setattr("app.providers.zhipu.get_settings", lambda: mock_settings)
    with pytest.raises(ExternalServiceError, match="智谱API"):
        ZhipuEmbeddingProvider()


def test_zhipu_embed_query_happy(zhipu_embed):
    """embed_query 返回正确向量"""
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    zhipu_embed.client.embeddings.create = MagicMock(return_value=mock_resp)

    result = zhipu_embed.embed_query("test")
    assert result == [0.1, 0.2, 0.3]


def test_zhipu_embed_documents_happy(zhipu_embed):
    """embed_documents 批量返回"""
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.1]), MagicMock(embedding=[0.2])]
    zhipu_embed.client.embeddings.create = MagicMock(return_value=mock_resp)

    result = zhipu_embed.embed_documents(["a", "b"])
    assert result == [[0.1], [0.2]]


def test_zhipu_embed_api_error(zhipu_embed):
    """API 异常抛出 ExternalServiceError"""
    zhipu_embed.client.embeddings.create = MagicMock(side_effect=Exception("error"))
    with pytest.raises(ExternalServiceError, match="智谱Embedding"):
        zhipu_embed.embed_query("test")


# =========================================================================
# OpenAIStyleLLMProvider
# =========================================================================


@pytest.fixture
def openai_llm(monkeypatch):
    """构造 OpenAIStyleLLMProvider，mock 掉 OpenAI client"""
    mock_settings = MagicMock(
        openai_api_key="sk-test",
        openai_base_url="",
        openai_llm_model="",
        llm_model="gpt-4o-mini",
        llm_temperature=0.7,
        llm_max_tokens=2048,
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.openai_style.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.providers.openai_style.OpenAI", MagicMock)
    provider = OpenAIStyleLLMProvider()
    yield provider


def test_openai_llm_requires_key(monkeypatch):
    """缺失 api_key 时抛出 ExternalServiceError"""
    mock_settings = MagicMock(
        openai_api_key="",
        openai_base_url="",
    )
    monkeypatch.setattr("app.providers.openai_style.get_settings", lambda: mock_settings)
    with pytest.raises(ExternalServiceError, match="OPENAI_API_KEY"):
        OpenAIStyleLLMProvider()


def test_openai_llm_uses_openai_model_first(monkeypatch):
    """优先使用 openai_llm_model 而非公共 llm_model"""
    mock_settings = MagicMock(
        openai_api_key="sk-test",
        openai_base_url="",
        openai_llm_model="gpt-4o",
        llm_model="glm-4-flash",
        llm_temperature=0.7,
        llm_max_tokens=2048,
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.openai_style.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.providers.openai_style.OpenAI", MagicMock)
    provider = OpenAIStyleLLMProvider()
    assert provider.model == "gpt-4o"


def test_openai_llm_fallback_to_public_model(monkeypatch):
    """openai_llm_model 为空时 fallback 到 llm_model"""
    mock_settings = MagicMock(
        openai_api_key="sk-test",
        openai_base_url="",
        openai_llm_model="",
        llm_model="glm-4-flash",
        llm_temperature=0.7,
        llm_max_tokens=2048,
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.openai_style.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.providers.openai_style.OpenAI", MagicMock)
    provider = OpenAIStyleLLMProvider()
    assert provider.model == "glm-4-flash"


def test_openai_llm_chat_happy(openai_llm):
    """chat 返回文本"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="hello"))]
    openai_llm.client.chat.completions.create = MagicMock(return_value=mock_resp)

    result = openai_llm.chat([{"role": "user", "content": "hi"}])
    assert result == "hello"


def test_openai_llm_check_health_ok(openai_llm):
    """健康检查成功"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="hi"))]
    openai_llm.client.chat.completions.create = MagicMock(return_value=mock_resp)
    assert openai_llm.check_health() == "ok"


# =========================================================================
# OpenAIStyleEmbeddingProvider
# =========================================================================


@pytest.fixture
def openai_embed(monkeypatch):
    """构造 OpenAIStyleEmbeddingProvider"""
    mock_settings = MagicMock(
        openai_api_key="sk-test",
        openai_base_url="",
        openai_embedding_model="",
        embedding_model="text-embedding-3-small",
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.openai_style.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.providers.openai_style.OpenAI", MagicMock)
    provider = OpenAIStyleEmbeddingProvider()
    yield provider


def test_openai_embed_query_happy(openai_embed):
    """embed_query 返回正确向量"""
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.5, 0.6])]
    openai_embed.client.embeddings.create = MagicMock(return_value=mock_resp)

    result = openai_embed.embed_query("test")
    assert result == [0.5, 0.6]


# =========================================================================
# 工厂函数
# =========================================================================


def test_create_llm_provider_default_zhipu(monkeypatch):
    """默认返回 ZhipuLLMProvider"""
    mock_settings = MagicMock(
        llm_provider="zhipu",
        zhipu_api_key="test-key",
        llm_model="glm-4-flash",
        llm_temperature=0.7,
        llm_max_tokens=2048,
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.factory.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.providers.factory.ZhipuLLMProvider", MagicMock)

    provider = create_llm_provider()
    assert provider is not None


def test_create_llm_provider_unknown_type(monkeypatch):
    """未知 provider type 抛出 ValueError"""
    mock_settings = MagicMock(llm_provider="unknown_llm")
    monkeypatch.setattr("app.providers.factory.get_settings", lambda: mock_settings)

    with pytest.raises(ValueError, match="未知 provider type"):
        create_llm_provider()


def test_create_embedding_provider_unknown_type(monkeypatch):
    """未知 embedding provider type 抛出 ValueError"""
    mock_settings = MagicMock(embedding_provider="unknown_embed")
    monkeypatch.setattr("app.providers.factory.get_settings", lambda: mock_settings)

    with pytest.raises(ValueError, match="未知 provider type"):
        create_embedding_provider()


def test_create_llm_provider_override_type(monkeypatch):
    """显式指定 type 应返回对应 Provider 类型（需对应配置就绪）"""
    mock_settings = MagicMock(
        llm_provider="zhipu",
        zhipu_api_key="test-key",
        llm_model="glm-4-flash",
        llm_temperature=0.7,
        llm_max_tokens=2048,
        llm_timeout_s=30,
    )
    monkeypatch.setattr("app.providers.factory.get_settings", lambda: mock_settings)

    # 覆盖 _PROVIDER_MAP 中的 openai 指向 mock
    mock_provider_cls = MagicMock()
    monkeypatch.setitem(
        app.providers.factory._PROVIDER_MAP,
        "openai",
        (mock_provider_cls, MagicMock()),
    )

    provider = create_llm_provider(provider_type="openai")
    assert provider is not None
    mock_provider_cls.assert_called_once()
