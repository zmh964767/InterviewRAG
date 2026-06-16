"""管理员修改密码

POST /api/admin/change-password — 改密码（需有效 JWT，写回 .env）

放在独立文件避免和 auth.py 循环导入（auth.py 不依赖 deps_admin）。
"""

import hmac
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api import auth as auth_module
from app.api.deps_admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str


def _find_env_file() -> Path | None:
    """找到 .env 文件路径（向上回溯，参考 pydantic-settings 默认行为）"""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        env_path = parent / ".env"
        if env_path.exists():
            return env_path
    return None


def _write_env_password(env_path: Path, new_password: str) -> bool:
    """把新密码写回 .env 文件。返回是否成功。

    失败原因可能是文件只读 / 容器环境 .env 在镜像中 / 权限不足。
    """
    try:
        content = env_path.read_text(encoding="utf-8")
    except (OSError, PermissionError) as e:
        logger.warning(f"读取 .env 失败: {e}")
        return False

    new_line = f'ADMIN_PASSWORD={new_password}'
    pattern = re.compile(r'^ADMIN_PASSWORD=.*$', re.MULTILINE)

    if pattern.search(content):
        new_content = pattern.sub(new_line, content)
    else:
        if content and not content.endswith('\n'):
            content += '\n'
        new_content = content + new_line + '\n'

    try:
        env_path.write_text(new_content, encoding="utf-8")
        logger.info(f"已将新密码写回 {env_path}")
        return True
    except (OSError, PermissionError) as e:
        logger.warning(f"写 .env 失败: {e}")
        return False


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
)
async def change_password(request: ChangePasswordRequest):
    """修改管理员密码。

    1. 验证当前密码
    2. 写回 .env 文件（如果可写）
    3. 立刻更新内存覆盖（无需重启即生效）
    """
    current_pw = auth_module.get_current_password()

    if not hmac.compare_digest(request.current_password, current_pw):
        raise HTTPException(status_code=401, detail="当前密码错误")

    new_pw = request.new_password.strip()
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 个字符")
    if new_pw == request.current_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    env_path = _find_env_file()
    env_written = False
    if env_path:
        env_written = _write_env_password(env_path, new_pw)
    else:
        logger.warning("未找到 .env 文件，密码仅在内存中更新（重启后丢失）")

    auth_module.set_password_override(new_pw)

    if env_written:
        return ChangePasswordResponse(success=True, message="密码已修改并写入 .env")
    return ChangePasswordResponse(
        success=True,
        message="密码已修改（仅本次进程有效，重启后失效）",
    )
