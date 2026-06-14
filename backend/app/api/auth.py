"""管理员登录鉴权

POST /api/auth/login — 验证密码 → 签发 JWT（httpOnly cookie + JSON body）
POST /api/auth/logout — 登出（清除 cookie）
GET  /api/auth/me — 检查当前 cookie 是否有效

修改密码的端点在 app/api/admin_change_password.py（避免循环导入）

JWT 密钥在模块加载时自动初始化：
- 如果 settings.jwt_secret_key 为非空，使用该值
- 否则用 os.urandom(32).hex() 生成一次性密钥（重启后失效）
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from jose import jwt, JWTError
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# cookie 名称
COOKIE_NAME = "admin_token"

# 模块级缓存：JWT 密钥 + 密码覆盖
_SECRET_KEY: str = ""
_PASSWORD_OVERRIDE: str | None = None  # 改密码后的内存覆盖（重启失效前的最新值）


def _init_jwt_secret() -> str:
    """初始化 JWT 签名密钥"""
    settings = get_settings()
    if settings.jwt_secret_key:
        return settings.jwt_secret_key
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


def get_current_password() -> str:
    """获取当前生效的密码（内存覆盖 > settings.admin_password）"""
    return _PASSWORD_OVERRIDE if _PASSWORD_OVERRIDE is not None else get_settings().admin_password


def set_password_override(new_password: str | None) -> None:
    """设置内存密码覆盖（供 change-password 端点调用）"""
    global _PASSWORD_OVERRIDE
    _PASSWORD_OVERRIDE = new_password


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """管理员登录：验证密码 → 签发 JWT"""
    current_pw = get_current_password()

    if not current_pw:
        logger.error("admin_password 未配置！请设置 ADMIN_PASSWORD 环境变量")
        raise HTTPException(status_code=503, detail="服务未配置管理员密码，请联系管理员通过环境变量设置")

    if request.password != current_pw:
        logger.warning("管理员登录失败：密码错误")
        raise HTTPException(status_code=401, detail="密码错误")

    secret = _ensure_secret()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=get_settings().jwt_expire_minutes
    )

    payload = {
        "sub": "admin",
        "role": "admin",
        "exp": expire,
    }
    access_token = jwt.encode(payload, secret, algorithm=get_settings().jwt_algorithm)

    response = Response(
        status_code=200,
        content=LoginResponse(access_token=access_token).model_dump_json(),
        media_type="application/json",
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=get_settings().jwt_expire_minutes * 60,
        secure=False,  # dev 模式用 http; 生产部署时建议设为 True（需 https）
        path="/",
    )
    return response


@router.post("/auth/logout")
async def logout():
    """管理员登出：清除 httpOnly cookie"""
    response = Response(status_code=200, content='{"success":true}')
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )
    return response


@router.get("/auth/me")
async def auth_me(request: Request):
    """检查当前 cookie 是否有效（供前端页面加载时验证登录状态）"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        secret = _ensure_secret()
        settings = get_settings()
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
        return {"sub": payload.get("sub"), "role": payload.get("role")}
    except JWTError as e:
        logger.warning(f"JWT cookie 验证失败: {e}")
        raise HTTPException(status_code=401, detail="token 无效或已过期")
