"""FastAPI 应用入口"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core import db as db_module
from app.core.exceptions import AppError, ExternalServiceError
from app.models.database import Database
from app.services.rag_service import RAGService
from app.api import query, health, questions_public
from app.api import auth
from app.api import admin
from app.api import feedback as feedback_router

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：统一初始化 / 清理所有共享实例"""
    # 设置 HuggingFace 国内镜像（Re-ranker 模型下载）
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    settings = get_settings()
    logger.info(f"启动 InterviewRAG，ChromaDB 路径: {settings.chroma_persist_dir}")

    # 统一初始化共享实例
    db = Database()
    db_module.set_db(db)   # core/db.py 共享同一实例
    app.state.db = db
    app.state.rag = RAGService()

    yield

    # 清理
    db_module.close_db()
    logger.info("关闭 InterviewRAG")


app = FastAPI(
    title="InterviewRAG",
    description="基于 RAG 的面试题库问答系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置（从 settings 读取，部署时通过 .env 配置域名）
_cors_origins = get_settings().cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局请求超时中间件（SSE 流式端点豁免，由 provider 超时控制）
_TIMEOUT_EXEMPT_PATHS = {"/api/query"}


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    if request.url.path in _TIMEOUT_EXEMPT_PATHS:
        return await call_next(request)
    try:
        return await asyncio.wait_for(call_next(request), timeout=get_settings().request_timeout_s)
    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"detail": "请求超时"})


# 注册路由
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(questions_public.router, prefix="/api", tags=["questions"])
app.include_router(health.router, prefix="/api", tags=["health"])
# 公开反馈(POST /feedback)— prefix="/api",router 内部路径 /feedback
app.include_router(feedback_router.router, prefix="/api", tags=["feedback"])
app.include_router(admin.router)  # /api/admin/* — JWT 保护(含 feedback 管理端)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """全局应用异常处理"""
    logger.error(f"应用异常: {exc.message} (status={exc.status_code})")
    # ExternalServiceError 脱敏：不暴露内部服务细节
    detail = "外部服务暂时不可用" if isinstance(exc, ExternalServiceError) else exc.message
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """全局未知异常处理"""
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "status_code": 500},
    )


@app.get("/")
async def root():
    return {"message": "InterviewRAG API", "docs": "/docs"}
