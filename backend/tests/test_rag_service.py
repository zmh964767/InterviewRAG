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


# =====================================================================
# 11 个补充测试：覆盖 _retrieve / _process_results / _build_messages /
# query_stream / query 的多分支
# =====================================================================


@pytest.mark.asyncio
async def test_retrieve_multi_query_branch(rag_service):
    """multi_query_enabled=True 时走 multi_query_retriever.aretrieve"""
    rag_service.settings.multi_query_enabled = True
    # raw 格式：hybrid/multi_query 返回 {id, text, rrf_score}，_process_results 会解析
    raw_sources = [
        {"id": "1", "text": "题目：Q1\n\n答案：A1", "rrf_score": 0.9},
    ]
    expected = [
        {"id": "1", "question": "Q1", "answer": "A1", "category": "", "difficulty": "", "score": 0.9},
    ]
    rag_service.multi_query_retriever.aretrieve = AsyncMock(return_value=raw_sources)
    # reranker 不可用，跳过 rerank
    rag_service.reranker.is_available = MagicMock(return_value=False)

    result = await rag_service._retrieve("test query")

    rag_service.multi_query_retriever.aretrieve.assert_awaited_once_with(
        query="test query", top_k=rag_service.settings.retrieval_top_k,
    )
    rag_service.hybrid_retriever.retrieve.assert_not_called()
    assert result == expected


@pytest.mark.asyncio
async def test_retrieve_single_branch(rag_service):
    """multi_query_enabled=False 时走 hybrid_retriever.retrieve（单路）"""
    rag_service.settings.multi_query_enabled = False
    raw_sources = [
        {"id": "1", "text": "题目：Q1\n\n答案：A1", "rrf_score": 0.9},
    ]
    expected = [
        {"id": "1", "question": "Q1", "answer": "A1", "category": "", "difficulty": "", "score": 0.9},
    ]
    # 不要 mock run_in_executor，让它真跑；直接给 hybrid_retriever.retrieve 塞返回
    rag_service.hybrid_retriever.retrieve = MagicMock(return_value=raw_sources)
    rag_service.reranker.is_available = MagicMock(return_value=False)

    result = await rag_service._retrieve("test query")

    rag_service.hybrid_retriever.retrieve.assert_called_once_with(
        query="test query", top_k=rag_service.settings.retrieval_top_k,
    )
    rag_service.multi_query_retriever.aretrieve.assert_not_called()
    assert result == expected


@pytest.mark.asyncio
async def test_retrieve_reranker_unavailable(rag_service):
    """reranker.is_available() == False 时跳过 rerank"""
    rag_service.settings.multi_query_enabled = False
    raw_sources = [
        {"id": "1", "text": "题目：Q1\n\n答案：A1", "rrf_score": 0.9},
    ]
    expected = [
        {"id": "1", "question": "Q1", "answer": "A1", "category": "", "difficulty": "", "score": 0.9},
    ]
    rag_service.hybrid_retriever.retrieve = MagicMock(return_value=raw_sources)
    rag_service.reranker.is_available = MagicMock(return_value=False)
    rag_service.reranker.rerank = MagicMock(return_value=raw_sources)

    result = await rag_service._retrieve("test query")

    rag_service.reranker.rerank.assert_not_called()
    assert result == expected


def test_process_results_parses_format(rag_service):
    """_process_results 解析 "题目：X\\n\\n答案：Y" 格式"""
    raw = [
        {"text": "题目：什么是 RAG？\n\n答案：RAG 是检索增强生成。", "id": "1", "rrf_score": 0.8},
    ]
    sources = rag_service._process_results(raw)
    assert len(sources) == 1
    assert sources[0]["question"] == "什么是 RAG？"
    assert sources[0]["answer"] == "RAG 是检索增强生成。"
    assert sources[0]["score"] == 0.8


def test_process_results_score_priority(rag_service):
    """score 优先级：rerank_score > rrf_score > 0.0"""
    raw = [
        {"id": "a", "text": "题目：a\n\n答案：a", "rerank_score": 0.9},
        {"id": "b", "text": "题目：b\n\n答案：b", "rrf_score": 0.7},
        {"id": "c", "text": "题目：c\n\n答案：c"},
    ]
    sources = rag_service._process_results(raw)
    # 按 score 降序排：a(0.9) > b(0.7) > c(0.0)
    assert len(sources) == 3
    score_by_id = {s["id"]: s["score"] for s in sources}
    assert score_by_id["a"] == 0.9
    assert score_by_id["b"] == 0.7
    assert score_by_id["c"] == 0.0
    # 顺序按 score 降序
    assert [s["id"] for s in sources] == ["a", "b", "c"]


def test_build_messages_no_history(rag_service):
    """chat_history=None 时 messages 长度 == 2（system + user）"""
    messages = rag_service._build_messages("Q", "context text", None)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Q" in messages[1]["content"]


def test_build_messages_truncates_to_window(rag_service):
    """_build_messages 按 memory_window*2 截断 chat_history

    后端截断逻辑：chat_history[-memory_window*2:]
    memory_window=5 → 最多保留 10 条历史消息 + 1 system + 1 user = 12 条
    """
    # 15 条历史（>10），应该被截断到 10 条
    history_15 = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
        for i in range(15)
    ]
    messages = rag_service._build_messages("Q", "ctx", history_15)
    # system + 截断后的 history(10) + user = 12
    assert len(messages) == 12
    # 最后一条 user message 应该是当前问题
    assert messages[-1]["role"] == "user"
    assert "Q" in messages[-1]["content"]
    # 中间的 10 条 history 应该来自 history_15 的最后 10 条
    history_in_msg = messages[1:-1]
    assert len(history_in_msg) == 10
    assert history_in_msg[0]["content"] == "msg5"  # history_15[5]
    assert history_in_msg[-1]["content"] == "msg14"  # history_15[14]

    # 小于 memory_window*2 时全部包含
    history_3 = [{"role": "user", "content": f"small{i}"} for i in range(3)]
    messages2 = rag_service._build_messages("Q", "ctx", history_3)
    # system + 3 history + user = 5
    assert len(messages2) == 5


def test_build_messages_context_in_system(rag_service):
    """system/user 消息 content 包含参考资料（context）"""
    sources = [
        {"id": "1", "question": "Q1", "answer": "A1", "category": "基础", "score": 0.9},
    ]
    context = rag_service._build_context(sources)
    messages = rag_service._build_messages("什么是 RAG", context, None)
    # user 消息里包含 "参考资料" 字样（_build_context 输出以 "参考资料 1" 开头）
    user_content = messages[-1]["content"]
    assert "参考资料" in user_content
    assert "什么是 RAG" in user_content
    assert "Q1" in user_content or "A1" in user_content


@pytest.mark.asyncio
async def test_query_stream_happy_path(rag_service):
    """query_stream happy path：chat_stream 返回 async generator"""
    async def fake_stream(messages):
        yield "chunk1"
        yield "chunk2"
        yield "chunk3"

    rag_service._retrieve = AsyncMock(return_value=[
        {"id": "1", "question": "Q", "answer": "A", "category": "基础", "score": 0.9},
    ])
    rag_service.llm_service.chat_stream = fake_stream

    gen = await rag_service.query_stream("test query", [])
    # 拿到 _StreamWithSources 对象
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    assert chunks == ["chunk1", "chunk2", "chunk3"]
    # sources 挂在 gen 上
    assert len(gen.sources) == 1


@pytest.mark.asyncio
async def test_query_stream_llm_error(rag_service):
    """query_stream：chat_stream 抛异常时 async for 应当传播"""
    async def failing_stream(messages):
        raise RuntimeError("boom")
        # 不会到达这里，但语法上需要是 generator
        yield ""  # pragma: no cover

    rag_service._retrieve = AsyncMock(return_value=[])
    rag_service.llm_service.chat_stream = failing_stream

    gen = await rag_service.query_stream("test query", [])
    with pytest.raises(RuntimeError, match="boom"):
        async for _chunk in gen:
            pass


@pytest.mark.asyncio
async def test_query_llm_error(rag_service):
    """query：llm_service.chat 抛异常应当向上传播"""
    rag_service._retrieve = AsyncMock(return_value=[])
    rag_service.llm_service.chat = MagicMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await rag_service.query("test query")
