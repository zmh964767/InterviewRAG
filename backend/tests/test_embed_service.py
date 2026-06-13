"""EmbedService 单测"""

import pytest
from unittest.mock import MagicMock

from app.services.embed_service import EmbedService
from app.core.exceptions import ExternalServiceError


@pytest.fixture
def embed_service(monkeypatch):
    """构造 EmbedService，mock 掉 ZhipuAI client"""
    mock_settings = MagicMock(zhipu_api_key="test-key", embedding_model="embedding-3")
    monkeypatch.setattr("app.services.embed_service.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.services.embed_service.ZhipuAI", MagicMock)
    service = EmbedService()
    return service


def test_embed_query_happy(embed_service):
    """happy path: embed_query 返回正确向量"""
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    embed_service.client.embeddings.create = MagicMock(return_value=mock_resp)

    result = embed_service.embed_query("什么是微服务架构？")
    assert result == [0.1, 0.2, 0.3]


def test_embed_documents_happy(embed_service):
    """happy path: embed_documents 批量返回"""
    mock_resp = MagicMock()
    mock_resp.data = [
        MagicMock(embedding=[0.1, 0.2]),
        MagicMock(embedding=[0.3, 0.4]),
    ]
    embed_service.client.embeddings.create = MagicMock(return_value=mock_resp)

    result = embed_service.embed_documents(["Q1", "Q2"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_query_api_error(embed_service):
    """error path: API 调用失败抛出 ExternalServiceError"""
    embed_service.client.embeddings.create = MagicMock(side_effect=Exception("API error"))

    with pytest.raises(ExternalServiceError, match="智谱Embedding"):
        embed_service.embed_query("test")
