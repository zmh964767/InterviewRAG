"""管理员 JWT 验证依赖

用于管理端路由的 Depends 守卫：
```python
from app.api.deps_admin import require_admin

@router.get("/api/admin/stats", dependencies=[Depends(require_admin)])
async def admin_stats():
    ...
```
"""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.api.auth import _ensure_secret
from app.config import get_settings

logger = logging.getLogger(__name__)

# HTTPBearer 自动从 Authorization header 提取 Bearer token
_bearer_scheme = HTTPBearer(auto_error=False)


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
):
    """JWT 验证依赖：验证 token 有效且角色为 admin

    用法：加到 router 或单个 endpoint 的 dependencies 参数
    或直接作为 Depends(require_admin) 注入
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    settings = get_settings()

    try:
        secret = _ensure_secret()
        payload = jwt.decode(
            token, secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as e:
        logger.warning(f"JWT 验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证角色
    role = payload.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限",
        )

    return payload
