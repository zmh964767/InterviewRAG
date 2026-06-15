"""auth 登录限流单测

覆盖：
- 前 5 次失败正常返回 401
- 第 6 次失败返回 429
- 登录成功后限流计数清零
- 窗口过期后计数重置
- X-Forwarded-For 头提取 IP
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import (
    _check_rate_limit,
    _clear_rate_limit,
    _get_client_ip,
    _login_attempts,
    MAX_LOGIN_FAILS,
    LOGIN_WINDOW,
)


@pytest.fixture(autouse=True)
def _clean_attempts():
    """每个测试前清空限流状态"""
    _login_attempts.clear()
    yield
    _login_attempts.clear()


# ---- _get_client_ip ----


class TestGetClientIP:
    def test_x_forwarded_for(self):
        req = MagicMock()
        req.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(req) == "1.2.3.4"

    def test_x_forwarded_for_with_spaces(self):
        req = MagicMock()
        req.headers = {"X-Forwarded-For": "  10.0.0.1 , 10.0.0.2  "}
        assert _get_client_ip(req) == "10.0.0.1"

    def test_no_forwarded_for(self):
        req = MagicMock()
        req.headers = {}
        req.client.host = "127.0.0.1"
        assert _get_client_ip(req) == "127.0.0.1"

    def test_no_client(self):
        req = MagicMock()
        req.headers = {}
        req.client = None
        assert _get_client_ip(req) == "unknown"


# ---- _check_rate_limit ----


class TestCheckRateLimit:
    def test_first_fail_passes(self):
        """第 1 次失败不触发限流"""
        _check_rate_limit("1.2.3.4")  # 不抛异常
        assert _login_attempts["1.2.3.4"][0] == 1

    def test_fifth_fail_passes(self):
        """第 5 次失败仍允许（计数从 1 开始，5 次后 fails=5）"""
        for i in range(5):
            _check_rate_limit("1.2.3.4")
        assert _login_attempts["1.2.3.4"][0] == 5

    def test_sixth_fail_raises_429(self):
        """第 6 次失败触发 429"""
        for _ in range(5):
            _check_rate_limit("1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit("1.2.3.4")
        assert exc_info.value.status_code == 429

    def test_different_ips_independent(self):
        """不同 IP 的限流独立"""
        for _ in range(5):
            _check_rate_limit("1.1.1.1")
        # IP 2 仍然可以
        _check_rate_limit("2.2.2.2")  # 不抛
        assert _login_attempts["2.2.2.2"][0] == 1

    def test_window_expiry_resets(self):
        """窗口过期后计数重置"""
        _check_rate_limit("1.2.3.4")
        # 手动将窗口起点设为很久以前
        fails, _ = _login_attempts["1.2.3.4"]
        _login_attempts["1.2.3.4"] = (fails, time.monotonic() - LOGIN_WINDOW - 1)
        # 下一次调用应重置窗口
        _check_rate_limit("1.2.3.4")
        assert _login_attempts["1.2.3.4"][0] == 1


# ---- _clear_rate_limit ----


class TestClearRateLimit:
    def test_clears_existing(self):
        _check_rate_limit("1.2.3.4")
        assert "1.2.3.4" in _login_attempts
        _clear_rate_limit("1.2.3.4")
        assert "1.2.3.4" not in _login_attempts

    def test_clear_nonexistent_no_error(self):
        _clear_rate_limit("9.9.9.9")  # 不抛
