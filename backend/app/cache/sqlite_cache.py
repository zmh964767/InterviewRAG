"""SQLite 语义缓存后端

使用独立 SQLite 文件存储缓存条目。
embedding 以 JSON 序列化存储，查询时用 numpy cosine 计算相似度。
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度"""
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


class SQLiteCacheBackend:
    """SQLite 语义缓存后端

    特性：
    - 独立 SQLite 文件，与业务数据库隔离
    - JSON 序列化 embedding，调试友好
    - LRU 淘汰（超过 max_entries 删最旧的）
    - 惰性 TTL 过期（查询时跳过，cleanup_expired 定期清理）
    - 线程安全（写操作用锁）
    """

    def __init__(self, db_path: str | None = None, max_entries: int | None = None):
        settings = get_settings()
        self._db_path = db_path or settings.cache_db_path
        self._max_entries = max_entries or settings.cache_max_entries
        self._write_lock = threading.Lock()

        # 连接并建表
        from pathlib import Path
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_table()

        # 启动时清理过期条目
        expired = self.cleanup_expired()
        if expired > 0:
            logger.info(f"语义缓存启动：清理了 {expired} 条过期条目")

    def _init_table(self):
        """创建缓存表"""
        with self._write_lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_text TEXT NOT NULL,
                    query_embedding TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    similarity_threshold REAL NOT NULL,
                    hit_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_hit_at TEXT
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_created_at ON semantic_cache(created_at)"
            )
            self._conn.commit()

    def get(
        self, query_embedding: list[float], threshold: float
    ) -> dict | None:
        """语义查找最相似的缓存条目

        遍历所有未过期条目，计算 cosine 相似度，返回最高且超阈值的。
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=get_settings().cache_ttl_hours)

        rows = self._conn.execute(
            "SELECT id, query_text, query_embedding, result_json, hit_count "
            "FROM semantic_cache WHERE created_at >= ?",
            (cutoff.isoformat(),),
        ).fetchall()

        if not rows:
            return None

        best_id = None
        best_similarity = -1.0
        best_result = None
        best_query_text = ""

        for row in rows:
            cached_embedding = json.loads(row["query_embedding"])
            sim = _cosine_similarity(query_embedding, cached_embedding)
            if sim > best_similarity:
                best_similarity = sim
                best_id = row["id"]
                best_result = json.loads(row["result_json"])
                best_query_text = row["query_text"]

        if best_id is not None and best_similarity >= threshold:
            # 更新命中计数
            with self._write_lock:
                self._conn.execute(
                    "UPDATE semantic_cache SET hit_count = hit_count + 1, last_hit_at = ? WHERE id = ?",
                    (now.isoformat(), best_id),
                )
                self._conn.commit()

            best_result["similarity"] = round(best_similarity, 4)
            logger.info(
                f"cache_hit=true, similarity={best_similarity:.4f}, "
                f"query='{best_query_text[:50]}'"
            )
            return best_result

        logger.info(f"cache_miss, best_similarity={best_similarity:.4f}")
        return None

    def put(
        self,
        query_text: str,
        query_embedding: list[float],
        result: dict,
        ttl_hours: int,
    ) -> None:
        """写入缓存"""
        # 去掉 result 中的 similarity 字段（如果有），避免存入缓存
        clean_result = {k: v for k, v in result.items() if k != "similarity"}

        with self._write_lock:
            self._conn.execute(
                "INSERT INTO semantic_cache (query_text, query_embedding, result_json, similarity_threshold) "
                "VALUES (?, ?, ?, ?)",
                (
                    query_text,
                    json.dumps(query_embedding, ensure_ascii=False),
                    json.dumps(clean_result, ensure_ascii=False),
                    get_settings().cache_similarity_threshold,
                ),
            )
            self._conn.commit()

            # LRU 淘汰：超过 max_entries 时删最旧的
            count = self._conn.execute("SELECT COUNT(*) FROM semantic_cache").fetchone()[0]
            if count > self._max_entries:
                excess = count - self._max_entries
                self._conn.execute(
                    "DELETE FROM semantic_cache WHERE id IN "
                    "(SELECT id FROM semantic_cache ORDER BY created_at ASC LIMIT ?)",
                    (excess,),
                )
                self._conn.commit()
                logger.info(f"缓存 LRU 淘汰：删除 {excess} 条旧条目")

        logger.info(f"缓存写入: query='{query_text[:50]}', 条目数={min(count, self._max_entries)}")

    def invalidate(self) -> int:
        """全量清除缓存"""
        with self._write_lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM semantic_cache")
            count = cursor.fetchone()[0]
            self._conn.execute("DELETE FROM semantic_cache")
            self._conn.commit()
        logger.info(f"缓存已全量清除: {count} 条")
        return count

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=get_settings().cache_ttl_hours
        )
        with self._write_lock:
            cursor = self._conn.execute(
                "DELETE FROM semantic_cache WHERE created_at < ?",
                (cutoff.isoformat(),),
            )
            self._conn.commit()
            deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"缓存过期清理: {deleted} 条")
        return deleted

    def stats(self) -> dict:
        """返回缓存统计"""
        row = self._conn.execute(
            "SELECT COUNT(*) as total, COALESCE(SUM(hit_count), 0) as hit_count_total "
            "FROM semantic_cache"
        ).fetchone()

        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=get_settings().cache_ttl_hours
        )
        expired_row = self._conn.execute(
            "SELECT COUNT(*) FROM semantic_cache WHERE created_at < ?",
            (cutoff.isoformat(),),
        ).fetchone()

        return {
            "total": row["total"],
            "expired": expired_row[0],
            "hit_count_total": row["hit_count_total"],
        }
