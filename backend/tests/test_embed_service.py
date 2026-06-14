"""EmbedService 单测（Facade 层）

测试委托逻辑。Provider 实现本身的测试见 test_providers.py。
"""

import pytest
from unittest.mock import MagicMock

from app.services.embed_service import EmbedService
from app.providers import EmbeddingProvider


def _make_mock_embedding_provider():
    provider = MagicMock(spec=EmbeddingProvider)
    provider.embed_query.return_value = [0.1, 0.2]
    provider.embed_documents.return_value = [[0.1], [0.2]]
    return provider


@pytest.fixture
def embed_service():
    provider = _make_mock_embedding_provider()
    return EmbedService(provider=provider)


def test_embed_query_happy(embed_service):
    """embed_query 委托给 provider"""
    result = embed_service.embed_query("什么是微服务架构？")
    assert result == [0.1, 0.2]
    embed_service.provider.embed_query.assert_called_once_with("什么是微服务架构？")


def test_embed_documents_happy(embed_service):
    """embed_documents 委托给 provider"""
    result = embed_service.embed_documents(["Q1", "Q2"])
    assert result == [[0.1], [0.2]]
    embed_service.provider.embed_documents.assert_called_once_with(["Q1", "Q2"])


def test_default_provider():
    """不传 provider 时自动创建默认 Provider"""
    service = EmbedService()
    assert service.provider is not None
    assert isinstance(service.provider, EmbeddingProvider)