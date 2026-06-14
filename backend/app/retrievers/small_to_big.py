"""小块检索、大块生成策略 (Small-to-Big Retrieval)

核心思路：
- 小块（100-200字）：用于向量化和检索，语义更聚焦，匹配更精准
- 大块（500-1000字）：用于 LLM 生成，上下文更完整，回答更连贯

实现方式：
1. 导入时，每个大块拆成多个小块，记录 parent_id
2. 检索时，用小块匹配查询
3. 命中后，去重取回对应的大块送给 LLM
"""

import asyncio
import logging

from app.config import get_settings
from app.core.vectorstore import VectorStore

logger = logging.getLogger(__name__)


class SmallToBigRetriever:
    """小块检索、大块生成检索器"""

    def __init__(self, vector_store: VectorStore | None = None):
        self.settings = get_settings()
        self.vector_store = vector_store or VectorStore()

    def split_small_chunks(
        self,
        text: str,
        small_chunk_size: int = 150,
        overlap: int = 30,
    ) -> list[str]:
        """将文本拆成小块"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + small_chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
        return chunks

    def prepare_documents(
        self,
        question_id: str,
        question_text: str,
        answer_text: str,
        category: str,
        source: str,
    ) -> dict:
        """准备小块和大块数据

        Returns:
            {
                "parent_id": str,
                "parent_text": str,  # 大块，用于生成
                "children": [        # 小块列表，用于检索
                    {"id": str, "text": str, "metadata": dict}
                ]
            }
        """
        # 大块：完整的题目+答案
        parent_text = f"题目：{question_text}\n\n答案：{answer_text}"
        parent_id = question_id

        # 小块：拆分答案
        answer_chunks = self.split_small_chunks(
            answer_text,
            small_chunk_size=self.settings.chunk_size // 3,  # 小块约为大块的 1/3
            overlap=30,
        )

        children = []
        for i, chunk in enumerate(answer_chunks):
            child_id = f"{parent_id}_c{i}"
            # 每个小块都带上题目前缀，增强检索
            child_text = f"题目：{question_text}\n答案片段：{chunk}"
            children.append({
                "id": child_id,
                "text": child_text,
                "metadata": {
                    "parent_id": parent_id,
                    "parent_text": parent_text,
                    "question_id": question_id,
                    "category": category,
                    "source": source,
                    "chunk_index": i,
                },
            })

        return {
            "parent_id": parent_id,
            "parent_text": parent_text,
            "children": children,
        }

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        n_candidates: int = 20,
    ) -> list[dict]:
        """小块检索，返回大块

        Args:
            query: 查询文本
            top_k: 最终返回的大块数量
            n_candidates: 小块候选数量

        Returns:
            去重后的大块列表
        """
        # 1. 用小块检索
        results = self.vector_store.query(
            query_text=query,
            n_results=n_candidates,
        )

        if not results or not results.get("ids"):
            return []

        # 2. 收集命中的 parent_id，去重
        seen_parents: set[str] = set()
        parent_chunks: dict[str, dict] = {}

        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            parent_id = meta.get("parent_id", results["ids"][0][i])

            if parent_id not in seen_parents:
                seen_parents.add(parent_id)
                parent_chunks[parent_id] = {
                    "id": meta.get("question_id", parent_id),
                    "text": meta.get("parent_text", results["documents"][0][i]),
                    "category": meta.get("category", ""),
                    "source": meta.get("source", ""),
                    "score": round(1 - results["distances"][0][i], 4),
                    "strategy": "small_to_big",
                }

        # 3. 按分数排序，返回 top_k
        sorted_chunks = sorted(
            parent_chunks.values(),
            key=lambda x: x["score"],
            reverse=True,
        )

        return sorted_chunks[:top_k]

    async def aretrieve(
        self,
        query: str,
        top_k: int = 5,
        n_candidates: int = 20,
    ) -> list[dict]:
        """Async 入口，async 上下文使用。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.retrieve(query=query, top_k=top_k, n_candidates=n_candidates),
        )
