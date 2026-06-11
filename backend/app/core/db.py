"""Database 模块级单例

所有需要访问 SQLite 的模块共享此实例，避免多连接写入时 "database is locked"。
在 main.py lifespan 里通过 set_db() 初始化。
"""

from app.models.database import Database

_db: Database | None = None


def set_db(db: Database) -> None:
    """lifespan 里调用，注入共享实例"""
    global _db
    _db = db


def get_db() -> Database:
    """返回共享的 Database 单例（懒初始化兜底）"""
    global _db
    if _db is None:
        _db = Database()
    return _db


def close_db() -> None:
    """lifespan shutdown 里调用"""
    global _db
    if _db is not None:
        _db.close()
        _db = None
