"""服务端文件路径白名单校验

防止路径遍历攻击：限制所有 ingest 的服务端路径必须在 ./data 目录下，
且必须是相对路径、不能包含 ..、不能是符号链接。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 白名单根目录（绝对路径）
SAFE_DATA_DIR = Path("./data").resolve()


class PathGuardError(ValueError):
    """路径不安全（拒绝访问）"""


def validate_safe_path(rel_path: str) -> Path:
    """校验并返回安全的绝对路径

    Args:
        rel_path: 用户提供的相对路径

    Returns:
        校验通过后的绝对路径

    Raises:
        PathGuardError: 路径不满足安全要求
    """
    if not rel_path or not rel_path.strip():
        raise PathGuardError("路径不能为空")

    p = Path(rel_path)

    if p.is_absolute() or rel_path[0] == "/" or (len(rel_path) >= 2 and rel_path[1] == ":"):
        logger.warning(f"拒绝绝对路径: {rel_path}")
        raise PathGuardError("绝对路径被拒绝")

    if ".." in p.parts:
        logger.warning(f"拒绝包含 .. 的路径: {rel_path}")
        raise PathGuardError("包含 .. 的路径被拒绝")

    target = (SAFE_DATA_DIR / rel_path).resolve()

    # resolve 后必须仍在 SAFE_DATA_DIR 内（防止 symlink 跳出）
    if not str(target).startswith(str(SAFE_DATA_DIR)):
        logger.warning(f"拒绝路径逃逸: {rel_path} -> {target}")
        raise PathGuardError("路径逃逸到 data 目录外")

    if target.exists() and target.is_symlink():
        logger.warning(f"拒绝符号链接: {rel_path}")
        raise PathGuardError("符号链接被拒绝")

    return target
