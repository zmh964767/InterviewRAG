"""语义缓存集成测试

测试 RAGService 与 SemanticCache 的集成：
- 缓存命中时直接返回
- 缓存未命中时走正常 RAG 链路并写入缓存
- cache_enabled=False 时跳过缓存
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.rag_service import RAGService


@pytest.fixture
def mock_cache():
    """模拟缓存后端"""
    cache = MagicMock()
    cache.get.return_value = None  # 默认未命中
    cache.put.return_value = None
    cache.invalidate.return_value = 0
    cache.stats.return_value = {"total": 0, "expired": 0, "hit_count_total": 0}
    return cache


@pytest.fixture
def mock_embed_provider():
    """模拟 Embedding Provider"""
    provider = MagicMock()
    provider.embed_query.return_value = [0.1, 0.2, 0.3]
    return provider


@pytest.fixture
def rag_with_cache(monkeypatch, mock_cache, mock_embed_provider):
    """构造带缓存的 RAGService，mock 掉所有子服务"""
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
        cache_enabled=True,
        cache_similarity_threshold=0.95,
        cache_ttl_hours=24,
        cache_max_entries=100,
        cache_db_path=":memory:",
    )
    monkeypatch.setattr("app.services.rag_service.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.services.rag_service.VectorStore", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.HybridRetriever", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.BGEReranker", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.LLMService", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.QueryRewriter", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.MultiQueryRetriever", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.SQLiteCacheBackend", lambda *a, **kw: mock_cache)
    monkeypatch.setattr("app.services.rag_service.create_embedding_provider", lambda: mock_embed_provider)

    service = RAGService()
    service.cache = mock_cache
    service.embed_provider = mock_embed_provider
    return service


@pytest.fixture
def rag_no_cache(monkeypatch, mock_embed_provider):
    """构造 cache_enabled=False 的 RAGService"""
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
        cache_enabled=False,
        cache_similarity_threshold=0.95,
        cache_ttl_hours=24,
        cache_max_entries=100,
        cache_db_path=":memory:",
    )
    monkeypatch.setattr("app.services.rag_service.get_settings", lambda: mock_settings)
    monkeypatch.setattr("app.services.rag_service.VectorStore", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.HybridRetriever", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.BGEReranker", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.LLMService", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.QueryRewriter", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.MultiQueryRetriever", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.services.rag_service.create_embedding_provider", lambda: mock_embed_provider)

    service = RAGService()
    service.cache = None
    service.embed_provider = mock_embed_provider
    return service


@pytest.mark.asyncio
async def test_query_cache_hit(rag_with_cache, mock_cache):
    """缓存命中时直接返回缓存结果，不走 RAG 链路"""
    cached_result = {
        "answer": "Redis 是内存数据库",
        "sources": [{"id": "q1", "question": "什么是 Redis", "answer": "Redis 是...", "score": 0.95, "category": "DB"}],
        "similarity": 0.98,
    }
    mock_cache.get.return_value = cached_result

    result = await rag_with_cache.query("什么是 Redis")

    assert result["answer"] == "Redis 是内存数据库"
    assert result["sources"] == cached_result["sources"]
    # 验证没有调用 RAG 链路
    rag_with_cache.llm_service.chat.assert_not_called()
    rag_with_cache.hybrid_retriever.retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_query_cache_miss_then_rag_and_write(rag_with_cache, mock_cache, mock_embed_provider):
    """缓存未命中时走正常 RAG 链路，结果写入缓存"""
    mock_cache.get.return_value = None  # 未命中

    # mock RAG 链路
    rag_with_cache._retrieve = AsyncMock(return_value=[
        {"id": "q1", "question": "什么是 Redis", "answer": "Redis 是...", "category": "DB", "score": 0.9}
    ])
    rag_with_cache.llm_service.chat.return_value = "Redis 是一个开源的内存数据库"

    result = await rag_with_cache.query("什么是 Redis")

    assert result["answer"] == "Redis 是一个开源的内存数据库"
    # 验证写入了缓存
    mock_cache.put.assert_called_once()
    call_args = mock_cache.put.call_args
    assert call_args[0][0] == "什么是 Redis"  # query_text


@pytest.mark.asyncio
async def test_query_cache_disabled(rag_no_cache, mock_cache):
    """cache_enabled=False 时完全跳过缓存"""
    # mock RAG 链路
    rag_no_cache._retrieve = AsyncMock(return_value=[])
    rag_no_cache.llm_service.chat.return_value = "测试回答"

    result = await rag_no_cache.query("测试问题")

    assert result["answer"] == "测试回答"
    # cache 为 None，不会调用
    assert rag_no_cache.cache is None


@pytest.mark.asyncio
async def test_query_stream_cache_hit(rag_with_cache, mock_cache):
    """流式请求缓存命中时一次性返回完整答案"""
    cached_result = {
        "answer": "缓存的答案",
        "sources": [{"id": "q1", "question": "Q1", "answer": "A1", "score": 0.9, "category": "C"}],
        "similarity": 0.97,
    }
    mock_cache.get.return_value = cached_result

    gen = await rag_with_cache.query_stream("测试问题")

    # 收集流式输出
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)

    assert chunks == ["缓存的答案"]
    assert gen.sources == cached_result["sources"]
    # 没有调用 LLM
    rag_with_cache.llm_service.chat_stream.assert_not_called()


@pytest.mark.asyncio
async def test_query_stream_cache_miss(rag_with_cache, mock_cache):
    """流式请求缓存未命中时走正常 LLM 流"""
    mock_cache.get.return_value = None

    # mock 检索和 LLM 流
    rag_with_cache._retrieve = AsyncMock(return_value=[
        {"id": "q1", "question": "Q1", "answer": "A1", "category": "C", "score": 0.9}
    ])

    async def fake_stream(messages):
        for token in ["你", "好", "世", "界"]:
            yield token

    rag_with_cache.llm_service.chat_stream = fake_stream

    gen = await rag_with_cache.query_stream("测试问题")

    chunks = []
    async for chunk in gen:
        chunks.append(chunk)

    assert chunks == ["你", "好", "世", "界"]


@pytest.mark.asyncio
async def test_query_cache_exception_graceful(rag_with_cache, mock_cache):
    """缓存异常时降级走正常 RAG 链路"""
    mock_cache.get.side_effect = Exception("SQLite 连接失败")

    rag_with_cache._retrieve = AsyncMock(return_value=[
        {"id": "q1", "question": "Q1", "answer": "A1", "category": "C", "score": 0.9}
    ])
    rag_with_cache.llm_service.chat.return_value = "正常回答"

    result = await rag_with_cache.query("测试问题")

    # 应该正常返回，不抛异常
    assert result["answer"] == "正常回答"
