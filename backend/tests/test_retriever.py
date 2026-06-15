"""检索器测试"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from app.retrievers.hybrid_retriever import HybridRetriever
from app.rerankers.bge_reranker import BGEReranker


class TestBGEReranker:
    """BGE Re-ranker"""

    @pytest.mark.skip(reason="需要下载模型，CI 跳过")
    def test_reranker_initialization(self):
        reranker = BGEReranker()
        assert reranker.model_name == "BAAI/bge-reranker-base"
        assert isinstance(reranker.is_available(), bool)

    def test_reranker_without_model(self):
        reranker = BGEReranker()
        # Force model to not be loaded
        reranker.model = None
        reranker._loaded = True

        docs = [
            {"text": "doc1", "id": "1"},
            {"text": "doc2", "id": "2"},
        ]
        result = reranker.rerank("query", docs, top_k=2)
        # Should return original order when model not available
        assert len(result) == 2

    def test_reranker_empty_documents(self):
        reranker = BGEReranker()
        result = reranker.rerank("query", [], top_k=5)
        assert result == []


class TestHybridRetriever:
    """混合检索器"""

    def test_retriever_initialization(self):
        """检索器应该能初始化（需要 ChromaDB）"""
        # This test may fail if ChromaDB is not set up
        # It's more of an integration test
        try:
            from app.core.vectorstore import VectorStore
            vs = VectorStore()
            retriever = HybridRetriever(vs)
            assert retriever is not None
        except Exception:
            pytest.skip("ChromaDB not available")

    # ── _maybe_refresh 单元测试 ─────────────────────────────────────────────

    @staticmethod
    def _make_retriever(doc_count: int = 3):
        """构造带 mock vector_store 的 HybridRetriever（不碰 ChromaDB）"""
        mock_vs = MagicMock()
        docs = [f"doc_{i}" for i in range(doc_count)]
        metas = [{"category": "test"}] * doc_count
        mock_vs.get_all.return_value = {"documents": docs, "metadatas": metas}
        mock_vs.count.return_value = doc_count

        # patch get_settings 避免读 .env / pydantic 报错
        fake_settings = MagicMock()
        fake_settings.bm25_weight = 0.3
        fake_settings.bm25_refresh_ttl_seconds = 30.0

        with patch("app.retrievers.hybrid_retriever.get_settings", return_value=fake_settings):
            retriever = HybridRetriever(vector_store=mock_vs)
        return retriever, mock_vs

    def test_no_roundtrip_when_clean(self):
        """dirty=False 时，_maybe_refresh 不调 vector_store.count()"""
        retriever, mock_vs = self._make_retriever()
        # init 后 _dirty=False，且 _last_rebuild_at 已设置
        assert retriever._dirty is False

        mock_vs.count.reset_mock()  # 清掉 __init__ 期间可能的调用
        retriever._maybe_refresh()
        mock_vs.count.assert_not_called()

    def test_dirty_triggers_rebuild(self):
        """dirty=True 且 TTL 到期时，_maybe_refresh 触发重建并清 dirty"""
        retriever, mock_vs = self._make_retriever()

        retriever.invalidate()
        assert retriever._dirty is True
        # 强制 TTL 到期
        retriever._last_rebuild_at = 0.0
        # count 不变（仍为 3）→ 应该走 else 分支清 dirty，不重建
        mock_vs.count.return_value = 3
        mock_vs.get_all.reset_mock()

        retriever._maybe_refresh()
        assert retriever._dirty is False  # dirty 被清除
        mock_vs.get_all.assert_not_called()  # count 未变，不重建

    def test_ttl_expired_count_changed(self):
        """TTL 到期 + count 变化 → 重建"""
        retriever, mock_vs = self._make_retriever(doc_count=2)

        retriever.invalidate()
        retriever._last_rebuild_at = 0.0  # 强制 TTL 到期
        mock_vs.count.return_value = 5  # 文档数变了
        mock_vs.get_all.return_value = {
            "documents": [f"doc_{i}" for i in range(5)],
            "metadatas": [{"category": "test"}] * 5,
        }

        retriever._maybe_refresh()
        assert retriever._dirty is False
        assert retriever._index_doc_count == 5
        mock_vs.get_all.assert_called()  # 确实触发了重建

    def test_ttl_expired_count_unchanged(self):
        """TTL 到期但 count 不变 → 不重建，dirty 清除"""
        retriever, mock_vs = self._make_retriever(doc_count=3)

        retriever.invalidate()
        retriever._last_rebuild_at = 0.0  # 强制 TTL 到期
        mock_vs.count.return_value = 3  # 文档数没变
        mock_vs.get_all.reset_mock()

        retriever._maybe_refresh()
        assert retriever._dirty is False  # dirty 被清除
        mock_vs.get_all.assert_not_called()  # 不重建

    def test_concurrent_dirty_only_one_rebuild(self):
        """并发：两个线程同时 dirty=True → _build_bm25_index 只被调 1 次"""
        retriever, mock_vs = self._make_retriever(doc_count=3)

        retriever.invalidate()
        retriever._last_rebuild_at = 0.0  # 强制 TTL 到期
        mock_vs.count.return_value = 5  # count 变了，会触发重建
        mock_vs.get_all.return_value = {
            "documents": [f"doc_{i}" for i in range(5)],
            "metadatas": [{"category": "test"}] * 5,
        }

        # 统计 _build_bm25_index 实际被调次数
        call_count = {"n": 0}
        original_build = retriever._build_bm25_index

        def counting_build():
            call_count["n"] += 1
            original_build()

        retriever._build_bm25_index = counting_build

        barrier = threading.Barrier(2, timeout=5)
        errors = []

        def worker():
            try:
                barrier.wait()  # 两线程同时冲
                retriever._maybe_refresh()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"线程异常: {errors}"
        assert call_count["n"] == 1, f"期望 1 次重建，实际 {call_count['n']} 次"
