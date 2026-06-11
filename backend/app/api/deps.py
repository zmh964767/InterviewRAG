"""FastAPI 依赖注入

所有共享实例在 main.py lifespan 里初始化，路由通过 Depends 注入。
get_db 走 core/db.py 模块单例（lifespan 和测试都通过它设值）。
"""

from fastapi import Request

from app.core.db import get_db as _get_module_db
from app.models.database import Database
from app.services.rag_service import RAGService


def get_db() -> Database:
    return _get_module_db()


def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag
