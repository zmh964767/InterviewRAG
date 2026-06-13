"""管理端 API 路由汇总

将 admin_* 模块的路由统一集中到一个 router，方便 main.py 注册。
"""

from fastapi import APIRouter

from app.api import admin_ingest, admin_stats, admin_eval, admin_questions
from app.api import admin_change_password
from app.api import feedback

router = APIRouter(prefix="/api/admin", tags=["admin"])

router.include_router(admin_ingest.router)
router.include_router(admin_stats.router)
router.include_router(admin_eval.router)
router.include_router(admin_questions.router)
router.include_router(admin_change_password.router)
# 反馈管理端(GET /feedback, /feedback/stats) — feedback.router 自身已带 require_admin on these endpoints
router.include_router(feedback.router)
