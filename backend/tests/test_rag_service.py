"""RAGService 单测（纯函数 + query happy path）"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.rag_service import RAGService


@pytest.fixture
def rag_service(monkeypatch):
    """构造 RAGService，mock 掉所有子服务构造函数"""
    mock_settings = MagicMock(
        zhipu_api_key="test-key",
        llm_model="glm-4-flash",
        llm_temperature=0.7,
        llm_max_tokens=2048,
        embedding_model="embedding-3",
        multi_query_enabled=False,
        multi_query_n=3,
        multi_query_timeout_s=5,
        query_rewrite_prompt_variant="v1",
        retrieval_top_k=5,
        rerank_top_k=3,
        memory_window=5,
    )
    monkeypatch.setattr("app.services.rag_service.get_settings", lambda: mock_settings)
    # 用 lambda 返回 MagicMock 实例，避免 Python 3.13 的 InvalidSpecError
    # （MagicMock 作构造函数时，传入 MagicMock 参数会触发 spec 校验失败）
    monkeypatch.setattr("app.services.rag_service.VectorStore", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.HybridRetriever", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.BGEReranker", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.LLMService", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.EmbedService", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.QueryRewriter", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.MultiQueryRetriever", lambda *a, **kw: MagicMock())

    service = RAGService()
    return service


def test_build_context_empty_sources(rag_service):
    """空 sources 返回默认文本"""
    result = rag_service._build_context([])
    assert "暂无相关参考资料" in result


def test_build_context_with_sources(rag_service):
    """有 sources 时返回格式化文本"""
    sources = [
        {"id": "1", "question": "Q1", "answer": "A1", "category": "基础", "score": 0.9},
        {"id": "2", "question": "Q2", "answer": "A2", "category": "进阶", "score": 0.8},
    ]
    result = rag_service._build_context(sources)
    assert "Q1" in result
    assert "A1" in result
    assert "参考资料 1" in result


@pytest.mark.asyncio
async def test_query_happy_path(rag_service):
    """query 端到端 happy path（mock _retrieve + llm.chat）"""
    mock_sources = [
        {"id": "1", "question": "什么是微服务？", "answer": "微服务是...", "category": "架构", "score": 0.95},
    ]
    rag_service._retrieve = AsyncMock(return_value=mock_sources)
    rag_service.llm_service.chat = MagicMock(return_value="微服务是一种架构风格...")

    result = await rag_service.query("什么是微服务架构？")
    assert "answer" in result
    assert "sources" in result
    assert result["answer"] == "微服务是一种架构风格..."
