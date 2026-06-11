"""管理员登录鉴权

POST /api/auth/login — 验证密码 → 签发 JWT

JWT 密钥在模块加载时自动初始化：
- 如果 settings.jwt_secret_key 为非空，使用该值
- 否则用 os.urandom(32).hex() 生成一次性密钥（重启后失效）
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# 模块级缓存：JWT 密钥
_SECRET_KEY: str = ""


def _init_jwt_secret() -> str:
    """初始化 JWT 签名密钥"""
    settings = get_settings()
    if settings.jwt_secret_key:
        return settings.jwt_secret_key
    # 无配置时自动生成一次性密钥（重启后旧 token 失效）
    key = os.urandom(32).hex()
    logger.info(
        "JWT_SECRET_KEY 未配置，已自动生成一次性密钥 "
        "（服务重启后当前 token 将失效）"
    )
    return key


def _ensure_secret() -> str:
    """确保密钥已初始化（线程安全：CPython GIL 保护模块级变量赋值）"""
    global _SECRET_KEY
    if not _SECRET_KEY:
        _SECRET_KEY = _init_jwt_secret()
    return _SECRET_KEY


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """管理员登录：验证密码 → 签发 JWT"""
    settings = get_settings()

    if request.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="密码错误")

    # 安全警告：检测是否在使用默认密码
    if not settings.admin_password or settings.admin_password == "admin123":
        logger.warning(
            "管理员正在使用默认密码登录！生产环境务必通过 ADMIN_PASSWORD 环境变量配置"
        )

    secret = _ensure_secret()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )

    payload = {
        "sub": "admin",
        "role": "admin",
        "exp": expire,
    }
    access_token = jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)

    return LoginResponse(access_token=access_token)
