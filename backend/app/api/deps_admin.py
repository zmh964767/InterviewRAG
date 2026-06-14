"""管理员 JWT 验证依赖

用于管理端路由的 Depends 守卫：
```python
from app.api.deps_admin import require_admin

@router.get("/api/admin/stats", dependencies=[Depends(require_admin)])
async def admin_stats():
    ...
```

JWT 来源优先级：
1. httpOnly cookie `admin_token`（浏览器自动携带，更安全）
2. Authorization: Bearer <token> header（兼容 API 客户端/测试）
"""

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.api.auth import COOKIE_NAME, _ensure_secret
from app.config import get_settings

logger = logging.getLogger(__name__)

# HTTPBearer 自动从 Authorization header 提取 Bearer token
_bearer_scheme = HTTPBearer(auto_error=False)


def _decode_jwt(token: str) -> dict:
    """解码 JWT token，返回 payload

    Raises:
        HTTPException 401: token 无效或已过期
    """
    settings = get_settings()
    try:
        secret = _ensure_secret()
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        logger.warning(f"JWT 验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = payload.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限",
        )

    return payload


def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
):
    """JWT 验证依赖：验证 token 有效且角色为 admin

    从 httpOnly cookie 或 Authorization header 读取 JWT。
    用法：加到 router 或单个 endpoint 的 dependencies 参数
    或直接作为 Depends(require_admin) 注入
    """
    token: str | None = None

    # 优先级 1: httpOnly cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        token = cookie_token

    # 优先级 2: Authorization header（覆盖 cookie，兼容 API 客户端）
    if credentials is not None:
        token = credentials.credentials

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _decode_jwt(token)
