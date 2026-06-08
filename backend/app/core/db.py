"""Database 模块级单例

所有需要访问 SQLite 的模块共享此实例，避免多连接写入时 "database is locked"。
"""

from app.models.database import Database

_db: Database | None = None


def get_db() -> Database:
    """返回共享的 Database 单例"""
    global _db
    if _db is None:
        _db = Database()
    return _db
