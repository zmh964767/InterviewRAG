"""BGE Re-ranker

使用 BAAI/bge-reranker 对检索结果进行重排序。
注意：首次使用需要下载模型（约 1.1GB）。
"""


import structlog

logger = structlog.get_logger(__name__)


class BGEReranker:
    """BGE 交叉编码器重排序（懒加载，不阻塞启动）"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self.model = None
        self._loaded = False

    def _ensure_loaded(self):
        """懒加载模型（仅在模型已下载时加载，不主动下载）"""
        if self._loaded:
            return
        self._loaded = True
        # 评估场景可通过 SKIP_RERANKER=1 跳过加载（Windows 加载卡死）
        import os
        if os.environ.get("SKIP_RERANKER", "").lower() in ("1", "true", "yes"):
            logger.info("reranker_skipped", reason="SKIP_RERANKER env set")
            return
        try:
            from pathlib import Path
            cache_dir = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
            model_dir = cache_dir / "hub" / f"models--{self.model_name.replace('/', '--')}"
            if not model_dir.exists():
                logger.warning("reranker_model_not_found", model=self.model_name)
                return

            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            logger.info("reranker_loaded", model=self.model_name)
        except ImportError:
            logger.error("reranker_import_failed", fix="pip install sentence-transformers")
        except Exception as e:
            logger.error("reranker_load_failed", error=str(e))

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        """对文档重排序"""
        self._ensure_loaded()

        if not self.model:
            logger.warning("reranker_not_loaded")
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

            logger.info("rerank_complete", result_count=len(results))
            return results

        except Exception as e:
            logger.error("rerank_failed", error=str(e))
            return documents[:top_k]

    def is_available(self) -> bool:
        """检查模型是否可用"""
        self._ensure_loaded()
        return self.model is not None
