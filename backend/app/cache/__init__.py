"""语义缓存模块

提供 CacheBackend Protocol 和 SQLiteCacheBackend 实现。
"""

from app.cache.base import CacheBackend
from app.cache.sqlite_cache import SQLiteCacheBackend

__all__ = ["CacheBackend", "SQLiteCacheBackend"]
