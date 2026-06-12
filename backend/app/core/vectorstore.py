"""ChromaDB 向量存储封装

使用智谱 API 做 embedding，不依赖 ChromaDB 默认的 ONNX 模型。
"""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from app.config import get_settings

logger = logging.getLogger(__name__)

# Collection 名称
COLLECTION_NAME = "interview_questions"


class ZhipuEmbeddingFunction(EmbeddingFunction):
    """使用智谱 API 的 embedding 函数"""

    def __init__(self):
        from zhipuai import ZhipuAI
        settings = get_settings()
        self.client = ZhipuAI(api_key=settings.zhipu_api_key)
        self.model = settings.embedding_model

    def __call__(self, input: Documents) -> Embeddings:
        """将文本列表转为向量列表"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=input,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"智谱 Embedding 调用失败: {e}")
            raise


class VectorStore:
    """ChromaDB 向量存储"""

    def __init__(self):
        settings = get_settings()
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # 使用智谱 embedding 函数
        self.embed_fn = ZhipuEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embed_fn,
        )
        logger.info(f"ChromaDB 已连接，当前文档数: {self.collection.count()}")

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        embeddings: list[list[float]] | None = None,
    ):
        """添加文档到向量存储"""
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info(f"已添加 {len(ids)} 个文档，当前总数: {self.collection.count()}")

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        query_embedding: list[float] | None = None,
    ) -> dict:
        """语义检索"""
        kwargs = {
            "query_texts": [query_text] if query_embedding is None else None,
            "query_embeddings": [query_embedding] if query_embedding else None,
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }

        results = self.collection.query(**kwargs)
        return results

    def count(self) -> int:
        """返回文档数量"""
        return self.collection.count()

    def delete_all(self):
        """清空所有文档"""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embed_fn,
        )
        logger.info("已清空所有文档")

    def delete_by_id(self, question_id: str) -> bool:
        """根据 ID 删除单条向量

        Returns:
            True 表示成功（ChromaDB 不会因 ID 不存在而报错）
        """
        self.collection.delete(ids=[question_id])
        logger.info(f"已删除 ChromaDB 文档: {question_id}")
        return True

    def delete_by_ids(self, question_ids: list[str]) -> int:
        """批量删除向量

        Args:
            question_ids: 要删除的题目 ID 列表

        Returns:
            删除的 ID 数量
        """
        if not question_ids:
            return 0
        self.collection.delete(ids=question_ids)
        logger.info(f"已删除 ChromaDB 文档: {len(question_ids)} 条")
        return len(question_ids)

    def get_all(self) -> dict:
        """获取所有文档"""
        return self.collection.get(include=["documents", "metadatas"])
