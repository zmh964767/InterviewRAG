"""MultiQueryRetriever 单测

覆盖：去重/score 取 max/matched_queries 累加/top_k 裁剪/同 question 多 chunk 保留。
"""

import pytest
from unittest.mock import Mock

from app.retrievers.hybrid_retriever import HybridRetriever
from app.retrievers.multi_query_retriever import MultiQueryRetriever


@pytest.fixture
def mock_hybrid():
    """Mock HybridRetriever.retrieve()"""
    return Mock(spec=HybridRetriever)


@pytest.fixture
def retriever(mock_hybrid):
    """MultiQueryRetriever without rewriter（测试 retrieve_with_queries）"""
    return MultiQueryRetriever(hybrid=mock_hybrid, n=3, top_k=20)


def test_returns_empty_for_empty_queries(retriever, mock_hybrid):
    """空 queries 列表：直接返回空，不调 hybrid"""
    result = retriever.retrieve_with_queries([])
    assert result == []
    mock_hybrid.retrieve.assert_not_called()


def test_dedup_by_chunk_id(retriever, mock_hybrid):
    """同一 chunk id 在两路都被命中：去重保留一份"""
    mock_hybrid.retrieve.side_effect = [
        [{"id": "doc1", "text": "A", "rrf_score": 0.8}],
        [{"id": "doc1", "text": "A", "rrf_score": 0.7}],
        [{"id": "doc2", "text": "B", "rrf_score": 0.5}],
    ]
    result = retriever.retrieve_with_queries(["q1", "q2", "q3"], top_k=10)
    # doc1 / doc2 各 1 份
    assert len(result) == 2
    assert {d["id"] for d in result} == {"doc1", "doc2"}


def test_score_takes_max(retriever, mock_hybrid):
    """同 chunk 多次命中：score 取 max"""
    mock_hybrid.retrieve.side_effect = [
        [{"id": "doc1", "text": "A", "rrf_score": 0.8}],
        [{"id": "doc1", "text": "A", "rrf_score": 0.7}],
        [{"id": "doc1", "text": "A", "rrf_score": 0.95}],
    ]
    result = retriever.retrieve_with_queries(["q1", "q2", "q3"], top_k=10)
    assert len(result) == 1
    assert result[0]["id"] == "doc1"
    assert result[0]["rrf_score"] == 0.95


def test_matched_queries_accumulates(retriever, mock_hybrid):
    """同一 doc 命中多路：matched_queries 累加"""
    mock_hybrid.retrieve.side_effect = [
        [{"id": "doc1", "text": "A", "rrf_score": 0.8}],
        [{"id": "doc1", "text": "A", "rrf_score": 0.7}],
        [],
    ]
    result = retriever.retrieve_with_queries(["q1", "q2", "q3"], top_k=10)
    assert result[0]["matched_queries"] == ["q1", "q2"]


def test_top_k_truncation(retriever, mock_hybrid):
    """top_k 裁剪：合并后多余 entry 被裁掉"""
    mock_hybrid.retrieve.side_effect = [
        [{"id": f"doc{i}", "text": f"text{i}", "rrf_score": 0.9 - i * 0.1} for i in range(5)],
        [{"id": f"doc{i + 10}", "text": f"text{i + 10}", "rrf_score": 0.5 - i * 0.1} for i in range(5)],
    ]
    result = retriever.retrieve_with_queries(["q1", "q2"], top_k=3)
    assert len(result) == 3
    # 按 rrf_score 降序
    scores = [d["rrf_score"] for d in result]
    assert scores == sorted(scores, reverse=True)


def test_same_question_different_chunks_kept(retriever, mock_hybrid):
    """同一 question 的多个 chunk（不同 chunk_id）作为独立 entry 保留"""
    # 模拟：同一 question 被切成 2 个 chunk，2 个变体各自命中不同 chunk
    mock_hybrid.retrieve.side_effect = [
        [
            {"id": "q42_chunk0", "text": "...", "rrf_score": 0.8},
            {"id": "q42_chunk1", "text": "...", "rrf_score": 0.6},
        ],
        [
            {"id": "q42_chunk1", "text": "...", "rrf_score": 0.7},  # chunk1 又命中
            {"id": "q99_chunk0", "text": "...", "rrf_score": 0.4},
        ],
    ]
    result = retriever.retrieve_with_queries(["q1", "q2"], top_k=10)
    # q42_chunk0 + q42_chunk1 + q99_chunk0 = 3 个独立 entry
    assert len(result) == 3
    ids = {d["id"] for d in result}
    assert ids == {"q42_chunk0", "q42_chunk1", "q99_chunk0"}
    # q42_chunk1 命中 2 路，matched_queries 累加
    chunk1 = next(d for d in result if d["id"] == "q42_chunk1")
    assert chunk1["matched_queries"] == ["q1", "q2"]
    # score 取 max (0.7)
    assert chunk1["rrf_score"] == 0.7


def test_hybrid_failure_on_one_query_continues(retriever, mock_hybrid):
    """某一路 hybrid 失败：不影响其他路（空结果）"""
    mock_hybrid.retrieve.side_effect = [
        [{"id": "doc1", "text": "A", "rrf_score": 0.8}],
        Exception("ChromaDB 挂了"),
        [{"id": "doc2", "text": "B", "rrf_score": 0.5}],
    ]
    result = retriever.retrieve_with_queries(["q1", "q2", "q3"], top_k=10)
    # q1 + q3 命中，q2 失败被吞
    assert len(result) == 2
    assert {d["id"] for d in result} == {"doc1", "doc2"}


def test_doc_without_id_is_skipped(retriever, mock_hybrid):
    """doc 没有 id 字段：跳过，不入库"""
    mock_hybrid.retrieve.side_effect = [
        [
            {"id": "doc1", "text": "A", "rrf_score": 0.8},
            {"text": "no-id", "rrf_score": 0.9},  # 无 id
        ],
    ]
    result = retriever.retrieve_with_queries(["q1"], top_k=10)
    assert len(result) == 1
    assert result[0]["id"] == "doc1"


def test_rerank_score_preferred_over_rrf(retriever, mock_hybrid):
    """doc 带 rerank_score 时优先用它（兼容 hybrid_retriever 输出）"""
    mock_hybrid.retrieve.side_effect = [
        [
            {"id": "doc1", "text": "A", "rerank_score": 0.95, "rrf_score": 0.5},
        ],
    ]
    result = retriever.retrieve_with_queries(["q1"], top_k=10)
    # rerank_score > rrf_score，应该用 rerank_score
    assert result[0]["rerank_score"] == 0.95


def test_retrieve_calls_rewriter(retriever, mock_hybrid):
    """retrieve(query) 入口：先调 rewriter.rewrite 再转发"""
    rewriter = Mock()
    rewriter.rewrite.return_value = ["原始 query", "变体一", "变体二"]
    retriever.set_rewriter(rewriter)
    mock_hybrid.retrieve.return_value = [{"id": "doc1", "text": "A", "rrf_score": 0.8}]

    result = retriever.retrieve("原始 query", top_k=5)

    rewriter.rewrite.assert_called_once_with("原始 query")
    assert mock_hybrid.retrieve.call_count == 3  # 3 个变体
    assert len(result) == 1


def test_retrieve_without_rewriter_raises():
    """retrieve() 没注入 rewriter：抛 RuntimeError"""
    retriever = MultiQueryRetriever(hybrid=Mock(), n=3, top_k=20)
    with pytest.raises(RuntimeError, match="rewriter 未注入"):
        retriever.retrieve("query")