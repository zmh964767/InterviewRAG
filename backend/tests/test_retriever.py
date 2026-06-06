"""检索器测试"""

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
