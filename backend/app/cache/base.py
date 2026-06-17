"""CacheBackend Protocol

语义缓存后端接口，可插拔替换（SQLite → Redis 等）。
业务层只依赖此 Protocol，不直接引用具体实现。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """语义缓存后端接口"""

    def get(
        self, query_embedding: list[float], threshold: float
    ) -> dict | None:
        """语义查找最相似的缓存条目

        Args:
            query_embedding: 查询文本的 embedding 向量
            threshold: 相似度阈值（0~1）

        Returns:
            命中时返回 {"answer": ..., "sources": [...], "similarity": float}
            未命中返回 None
        """
        ...

    def put(
        self,
        query_text: str,
        query_embedding: list[float],
        result: dict,
        ttl_hours: int,
    ) -> None:
        """写入缓存

        Args:
            query_text: 原始查询文本（调试/日志用）
            query_embedding: 查询文本的 embedding 向量
            result: 完整 RAG 结果 {"answer": ..., "sources": [...]}
            ttl_hours: TTL（小时），过期条目在查询时跳过
        """
        ...

    def invalidate(self) -> int:
        """全量清除缓存

        Returns:
            删除的条目数
        """
        ...

    def cleanup_expired(self) -> int:
        """清理过期条目

        Returns:
            删除的条目数
        """
        ...

    def stats(self) -> dict:
        """返回缓存统计

        Returns:
            {"total": int, "expired": int, "hit_count_total": int}
        """
        ...
