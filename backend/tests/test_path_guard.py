"""path_guard 单元测试"""

import os
from pathlib import Path

import pytest

from app.core.path_guard import PathGuardError, validate_safe_path


class TestValidateSafePath:
    """validate_safe_path 白名单校验"""

    def test_rejects_empty(self):
        with pytest.raises(PathGuardError, match="不能为空"):
            validate_safe_path("")

    def test_rejects_whitespace(self):
        with pytest.raises(PathGuardError, match="不能为空"):
            validate_safe_path("   ")

    def test_rejects_absolute_path(self):
        with pytest.raises(PathGuardError, match="绝对路径被拒绝"):
            validate_safe_path("/etc/passwd")

        with pytest.raises(PathGuardError, match="绝对路径被拒绝"):
            validate_safe_path("C:/Windows/System32")

    def test_rejects_double_dot(self):
        with pytest.raises(PathGuardError, match=r"\.\."):
            validate_safe_path("../escape.md")

        with pytest.raises(PathGuardError, match=r"\.\."):
            validate_safe_path("questions/../../escape.md")

    def test_rejects_symlink(self, tmp_path, monkeypatch):
        # 在白名单外创建真实文件
        real = tmp_path / "real.md"
        real.write_text("content", encoding="utf-8")

        # 在 data/ 下创建符号链接指向 real.md
        data_link = Path("./data") / "link.md"
        data_link.parent.mkdir(parents=True, exist_ok=True)
        try:
            if data_link.exists() or data_link.is_symlink():
                data_link.unlink()
            os.symlink(str(real), str(data_link))
            try:
                # 在 Windows 上 symlink resolve 后会跳出白名单，触发"逃逸"分支
                # 在 Linux 上 symlink 仍指向白名单内 target.is_symlink() 为 True
                with pytest.raises(PathGuardError, match="符号链接|逃逸"):
                    validate_safe_path("link.md")
            finally:
                if data_link.is_symlink():
                    data_link.unlink()
        except (OSError, NotImplementedError):
            pytest.skip("symlink not supported on this platform")

    def test_accepts_normal_relative(self, tmp_path, monkeypatch):
        # 用临时目录覆盖白名单
        import app.core.path_guard as pg

        monkeypatch.setattr(pg, "SAFE_DATA_DIR", tmp_path.resolve())

        target = tmp_path / "questions.md"
        target.write_text("content", encoding="utf-8")

        result = validate_safe_path("questions.md")
        assert result == target.resolve()

    def test_accepts_nested_relative(self, tmp_path, monkeypatch):
        import app.core.path_guard as pg

        monkeypatch.setattr(pg, "SAFE_DATA_DIR", tmp_path.resolve())

        nested = tmp_path / "raw" / "questions.md"
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text("content", encoding="utf-8")

        result = validate_safe_path("raw/questions.md")
        assert result == nested.resolve()

    def test_rejects_path_escape_after_resolve(self, tmp_path, monkeypatch):
        """即使路径用 symlink 跳出也要被拒"""
        # 这里我们直接构造一个不存在但 resolve 后跑出白名单的路径
        import app.core.path_guard as pg

        monkeypatch.setattr(pg, "SAFE_DATA_DIR", tmp_path.resolve())

        # 直接传 ".." 会被 parts 检查拦下；这里测试 parts 不含 .. 但 resolve 后跳出
        # 在 data/ 父目录创建一个子目录，传入 ../sibling.md 会被 parts 检查拦下
        # 所以我们通过 symlink 模拟（在支持 symlink 的平台上）
        try:
            sibling = tmp_path.parent / "sibling.md"
            link = tmp_path / "sneaky.md"
            if link.exists() or link.is_symlink():
                link.unlink()
            os.symlink(str(sibling), str(link))
            with pytest.raises(PathGuardError, match="符号链接|逃逸"):
                validate_safe_path("sneaky.md")
            if link.is_symlink():
                link.unlink()
        except (OSError, NotImplementedError):
            pytest.skip("symlink not supported on this platform")
