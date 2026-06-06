"""BGE Re-ranker

使用 BAAI/bge-reranker 对检索结果进行重排序。
注意：首次使用需要下载模型（约 1.1GB）。
"""

import logging

logger = logging.getLogger(__name__)


class BGEReranker:
    """BGE 交叉编码器重排序（懒加载，不阻塞启动）"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self.model = None
        self._loaded = False

    def _ensure_loaded(self):
        """懒加载模型（首次调用时加载）"""
        if self._loaded:
            return
        self._loaded = True
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            logger.info(f"Re-ranker 模型已加载: {self.model_name}")
        except ImportError:
            logger.error(
                "sentence-transformers 未安装，请运行: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error(f"加载 Re-ranker 模型失败: {e}")

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        """对文档重排序"""
        self._ensure_loaded()

        if not self.model:
            logger.warning("Re-ranker 模型未加载，返回原始顺序")
            return documents[:top_k]

        if not documents:
            return []

        try:
            pairs = [(query, doc.get("text", "")) for doc in documents]
            scores = self.model.predict(pairs)
            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            results = []
            for doc, score in scored_docs[:top_k]:
                doc["rerank_score"] = float(score)
                results.append(doc)

            logger.info(f"Re-ranking 完成，返回 {len(results)} 个文档")
            return results

        except Exception as e:
            logger.error(f"Re-ranking 失败: {e}")
            return documents[:top_k]

    def is_available(self) -> bool:
        """检查模型是否可用"""
        self._ensure_loaded()
        return self.model is not None
