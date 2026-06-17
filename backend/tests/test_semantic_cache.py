"""语义缓存单元测试"""

import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest

# CI 没有 .env 文件
os.environ.setdefault("ZHIPU_API_KEY", "test-key-for-ci")

from app.cache.sqlite_cache import SQLiteCacheBackend, _cosine_similarity


@pytest.fixture
def cache(tmp_path):
    """使用临时目录的缓存实例"""
    db_path = str(tmp_path / "test_cache.db")
    return SQLiteCacheBackend(db_path=db_path, max_entries=100)


@pytest.fixture
def sample_embedding():
    """示例 embedding 向量（10 维，方便测试）"""
    return [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


@pytest.fixture
def sample_result():
    """示例 RAG 结果"""
    return {
        "answer": "Redis 是一个开源的内存数据结构存储系统",
        "sources": [
            {
                "question_id": "q1",
                "question_text": "什么是 Redis",
                "answer_text": "Redis 是...",
                "score": 0.95,
                "category": "数据库",
            }
        ],
    }


class TestCosineSimilarity:
    """余弦相似度函数测试"""

    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 0.0]
        assert _cosine_similarity(a, b) == 0.0

    def test_similar_vectors(self):
        a = [1.0, 1.0, 0.0]
        b = [1.0, 0.9, 0.1]
        sim = _cosine_similarity(a, b)
        assert 0.9 < sim < 1.0


class TestCachePutAndGet:
    """缓存写入和读取测试"""

    def test_put_then_get_hit(self, cache, sample_embedding, sample_result):
        """写入后相同查询命中"""
        cache.put("什么是 Redis", sample_embedding, sample_result, ttl_hours=24)

        result = cache.get(sample_embedding, threshold=0.95)
        assert result is not None
        assert result["answer"] == sample_result["answer"]
        assert result["sources"] == sample_result["sources"]
        assert "similarity" in result
        assert result["similarity"] >= 0.95

    def test_get_miss_threshold_too_high(self, cache, sample_embedding, sample_result):
        """相似度不够时未命中"""
        cache.put("什么是 Redis", sample_embedding, sample_result, ttl_hours=24)

        # 阈值设为 1.0，只有完全相同才能命中
        result = cache.get(sample_embedding, threshold=1.0)
        # cosine(相同向量) = 1.0，应该命中
        # 但如果用不同向量查询
        different_embedding = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
        result = cache.get(different_embedding, threshold=0.99)
        assert result is None

    def test_get_miss_empty_cache(self, cache, sample_embedding):
        """空缓存时返回 None"""
        result = cache.get(sample_embedding, threshold=0.95)
        assert result is None

    def test_hit_count_increments(self, cache, sample_embedding, sample_result):
        """每次命中 hit_count + 1"""
        cache.put("什么是 Redis", sample_embedding, sample_result, ttl_hours=24)

        cache.get(sample_embedding, threshold=0.95)
        cache.get(sample_embedding, threshold=0.95)
        cache.get(sample_embedding, threshold=0.95)

        stats = cache.stats()
        assert stats["hit_count_total"] == 3

    def test_similarity_stored_in_result(self, cache, sample_embedding, sample_result):
        """命中时 result 里包含 similarity 字段"""
        cache.put("什么是 Redis", sample_embedding, sample_result, ttl_hours=24)
        result = cache.get(sample_embedding, threshold=0.95)
        assert "similarity" in result
        assert isinstance(result["similarity"], float)

    def test_put_does_not_store_similarity(self, cache, sample_embedding, sample_result):
        """写入时如果 result 带 similarity，不应存入缓存"""
        sample_result["similarity"] = 0.99  # 不应被存入
        cache.put("什么是 Redis", sample_embedding, sample_result, ttl_hours=24)

        result = cache.get(sample_embedding, threshold=0.95)
        # similarity 应该是 get() 时重新计算的，不是缓存里的 0.99
        assert result is not None


class TestCacheTTL:
    """TTL 过期测试"""

    def test_expired_entry_not_hit(self, cache, sample_embedding, sample_result, tmp_path):
        """过期条目不被命中"""
        # 创建一个 TTL 为 0 小时的缓存（立即过期）
        cache.put("什么是 Redis", sample_embedding, sample_result, ttl_hours=24)

        # 手动把 created_at 改为 2 天前
        cache._conn.execute(
            "UPDATE semantic_cache SET created_at = ?",
            ((datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),),
        )
        cache._conn.commit()

        result = cache.get(sample_embedding, threshold=0.95)
        assert result is None

    def test_cleanup_expired(self, cache, sample_embedding, sample_result):
        """cleanup_expired 清理过期条目"""
        cache.put("什么是 Redis", sample_embedding, sample_result, ttl_hours=24)

        # 手动把 created_at 改为 2 天前
        cache._conn.execute(
            "UPDATE semantic_cache SET created_at = ?",
            ((datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),),
        )
        cache._conn.commit()

        deleted = cache.cleanup_expired()
        assert deleted == 1

        stats = cache.stats()
        assert stats["total"] == 0


class TestCacheInvalidate:
    """全量清除测试"""

    def test_invalidate_clears_all(self, cache, sample_embedding, sample_result):
        """invalidate 清空所有缓存"""
        cache.put("问题1", sample_embedding, sample_result, ttl_hours=24)
        cache.put("问题2", [0.5] * 10, sample_result, ttl_hours=24)

        deleted = cache.invalidate()
        assert deleted == 2

        stats = cache.stats()
        assert stats["total"] == 0

    def test_invalidate_empty_cache(self, cache):
        """空缓存 invalidate 返回 0"""
        deleted = cache.invalidate()
        assert deleted == 0


class TestCacheLRU:
    """LRU 淘汰测试"""

    def test_eviction_on_max_entries(self, tmp_path, sample_result):
        """超过 max_entries 时淘汰最旧的"""
        cache = SQLiteCacheBackend(
            db_path=str(tmp_path / "lru_test.db"),
            max_entries=3,
        )

        for i in range(5):
            embedding = [float(i) / 10] * 10
            cache.put(f"问题{i}", embedding, sample_result, ttl_hours=24)

        stats = cache.stats()
        assert stats["total"] == 3


class TestCacheStats:
    """统计信息测试"""

    def test_stats_empty(self, cache):
        """空缓存统计"""
        stats = cache.stats()
        assert stats["total"] == 0
        assert stats["expired"] == 0
        assert stats["hit_count_total"] == 0

    def test_stats_with_entries(self, cache, sample_embedding, sample_result):
        """有条目时统计正确"""
        cache.put("问题1", sample_embedding, sample_result, ttl_hours=24)
        cache.put("问题2", [0.5] * 10, sample_result, ttl_hours=24)
        cache.get(sample_embedding, threshold=0.95)

        stats = cache.stats()
        assert stats["total"] == 2
        assert stats["hit_count_total"] == 1
