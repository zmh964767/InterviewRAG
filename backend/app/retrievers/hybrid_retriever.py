"""混合检索器

融合向量检索（ChromaDB）和 BM25 关键词检索，
使用 RRF（Reciprocal Rank Fusion）算法合并结果。
"""

import logging
from rank_bm25 import BM25Okapi
import numpy as np

from app.config import get_settings
from app.core.vectorstore import VectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """混合检索器：向量 + BM25"""

    def __init__(self, vector_store: VectorStore | None = None):
        self.settings = get_settings()
        self.vector_store = vector_store or VectorStore()
        self.bm25_index: BM25Okapi | None = None
        self.corpus_texts: list[str] = []
        self.corpus_metas: list[dict] = []
        self._build_bm25_index()

    def _build_bm25_index(self):
        """构建 BM25 索引"""
        try:
            all_docs = self.vector_store.get_all()
            if not all_docs or not all_docs.get("documents"):
                logger.warning("ChromaDB 为空，无法构建 BM25 索引")
                return

            self.corpus_texts = all_docs["documents"]
            self.corpus_metas = all_docs["metadatas"] or [{}] * len(self.corpus_texts)

            # 分词（简单按字符切分，中文场景）
            tokenized = [list(text) for text in self.corpus_texts]
            self.bm25_index = BM25Okapi(tokenized)

            logger.info(f"BM25 索引已构建，文档数: {len(self.corpus_texts)}")
        except Exception as e:
            logger.error(f"构建 BM25 索引失败: {e}")

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        alpha: float | None = None,
    ) -> list[dict]:
        """混合检索

        Args:
            query: 查询文本
            top_k: 返回数量
            alpha: 向量权重（0-1），默认从配置读取

        Returns:
            按相关度排序的文档列表
        """
        if alpha is None:
            alpha = 1 - self.settings.bm25_weight

        # 1. 向量检索
        vector_results = self._vector_search(query, k=top_k * 2)

        # 2. BM25 检索
        bm25_results = self._bm25_search(query, k=top_k * 2)

        # 3. RRF 融合
        merged = self._reciprocal_rank_fusion(
            vector_results, bm25_results, alpha=alpha
        )

        return merged[:top_k]

    def _vector_search(self, query: str, k: int) -> list[dict]:
        """向量检索"""
        try:
            results = self.vector_store.query(query_text=query, n_results=k)
            if not results or not results.get("ids"):
                return []

            docs = []
            for i in range(len(results["ids"][0])):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                docs.append({
                    "id": meta.get("question_id", results["ids"][0][i]),
                    "text": results["documents"][0][i],
                    "metadata": meta,
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "source": "vector",
                })
            return docs
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []

    def _bm25_search(self, query: str, k: int) -> list[dict]:
        """BM25 检索"""
        if not self.bm25_index:
            return []

        try:
            tokenized_query = list(query)
            scores = self.bm25_index.get_scores(tokenized_query)

            # 获取 top-k 索引
            top_indices = np.argsort(scores)[::-1][:k]

            docs = []
            for idx in top_indices:
                if scores[idx] > 0:
                    meta = self.corpus_metas[idx] if idx < len(self.corpus_metas) else {}
                    docs.append({
                        "id": meta.get("question_id", f"doc_{idx}"),
                        "text": self.corpus_texts[idx],
                        "metadata": meta,
                        "bm25_score": float(scores[idx]),
                        "source": "bm25",
                    })
            return docs
        except Exception as e:
            logger.error(f"BM25 检索失败: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        alpha: float = 0.7,
        k: int = 60,
    ) -> list[dict]:
        """RRF 融合算法

        RRF(d) = sum( alpha / (k + rank_i) ) for each ranking list i
        """
        scores: dict[str, float] = {}
        doc_map: dict[str, dict] = {}

        # 向量检索结果
        for rank, doc in enumerate(vector_results):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0) + alpha / (k + rank + 1)
            doc_map[doc_id] = doc

        # BM25 检索结果
        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0) + (1 - alpha) / (k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        # 按融合分数排序
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids:
            doc = doc_map[doc_id]
            doc["rrf_score"] = scores[doc_id]
            results.append(doc)

        return results

    def refresh_index(self):
        """刷新 BM25 索引（数据更新后调用）"""
        self._build_bm25_index()
