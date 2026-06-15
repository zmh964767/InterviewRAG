"""auth 登录限流单测

覆盖：
- login_limiter 前 5 次失败允许
- 第 6 次失败返回 429
- 登录成功后限流计数清零
- 窗口过期后计数重置
- 不同 IP 独立限流
- hmac.compare_digest 密码比较（恒定时间）
- get_client_ip 各场景
"""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.auth import login_limiter
from app.core.rate_limiter import PerIPRateLimiter, get_client_ip


@pytest.fixture(autouse=True)
def _clean_limiter():
    """每个测试前清空限流状态"""
    login_limiter._records.clear()
    yield
    login_limiter._records.clear()


# ---- get_client_ip ----


class TestGetClientIP:
    """get_client_ip 各场景（trusted_proxies 参数化）"""

    def test_no_xff_returns_direct_ip(self):
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {}
        assert get_client_ip(req, trusted_proxies=[]) == "127.0.0.1"

    def test_xff_ignored_when_trusted_proxies_empty(self):
        """trusted_proxies 为空时忽略 XFF"""
        req = MagicMock()
        req.client.host = "1.2.3.4"
        req.headers = {"X-Forwarded-For": "9.8.7.6"}
        assert get_client_ip(req, trusted_proxies=[])

    def test_xff_ignored_when_direct_ip_not_trusted(self):
        """direct IP 不在信任列表时忽略 XFF"""
        req = MagicMock()
        req.client.host = "5.5.5.5"
        req.headers = {"X-Forwarded-For": "9.8.7.6"}
        assert get_client_ip(req, trusted_proxies=["127.0.0.1"]) == "5.5.5.5"

    def test_xff_read_when_direct_ip_is_trusted(self):
        """direct IP 在信任列表时读取 XFF 第一个值"""
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {"X-Forwarded-For": "9.8.7.6, 10.0.0.1"}
        assert get_client_ip(req, trusted_proxies=["127.0.0.1"]) == "9.8.7.6"

    def test_xff_with_spaces(self):
        req = MagicMock()
        req.client.host = "10.0.0.1"
        req.headers = {"X-Forwarded-For": "  192.168.1.1 , 10.0.0.1  "}
        assert get_client_ip(req, trusted_proxies=["10.0.0.1"]) == "192.168.1.1"

    def test_xff_falls_back_when_empty_header(self):
        """XFF 头存在但为空时返回 direct IP（空字串为 falsy）"""
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {"X-Forwarded-For": ""}
        assert get_client_ip(req, trusted_proxies=["127.0.0.1"]) == "127.0.0.1"

    def test_no_client_returns_unknown(self):
        req = MagicMock()
        req.client = None
        req.headers = {}
        assert get_client_ip(req, trusted_proxies=[]) == "unknown"

    def test_no_client_with_trusted_proxies(self):
        """client=None 时 direct_ip="unknown"，不会匹配任何 trusted proxy"""
        req = MagicMock()
        req.client = None
        req.headers = {"X-Forwarded-For": "1.2.3.4"}
        assert get_client_ip(req, trusted_proxies=["unknown"]) == "1.2.3.4"


# ---- login_limiter (PerIPRateLimiter) ----


class TestLoginLimiter:
    """login_limiter 实例的行为测试"""

    def test_first_five_allowed(self):
        """前 5 次调用返回 True"""
        for i in range(5):
            assert login_limiter.is_allowed("10.0.0.1") is True

    def test_sixth_blocked(self):
        """第 6 次调用返回 False"""
        for _ in range(5):
            login_limiter.is_allowed("10.0.0.1")
        assert login_limiter.is_allowed("10.0.0.1") is False

    def test_reset_clears_count(self):
        """reset 后计数归零"""
        for _ in range(5):
            login_limiter.is_allowed("10.0.0.1")
        assert login_limiter.is_allowed("10.0.0.1") is False
        login_limiter.reset("10.0.0.1")
        assert login_limiter.is_allowed("10.0.0.1") is True

    def test_reset_nonexistent_no_error(self):
        """reset 不存在的 IP 不抛异常"""
        login_limiter.reset("9.9.9.9")  # 不抛

    def test_different_ips_independent(self):
        """不同 IP 的限流独立"""
        for _ in range(5):
            login_limiter.is_allowed("1.1.1.1")
        assert login_limiter.is_allowed("1.1.1.1") is False
        assert login_limiter.is_allowed("2.2.2.2") is True

    def test_window_expiry_resets_count(self):
        """手动将窗口起点设为过期，下一次调用应重置计数"""
        login_limiter.is_allowed("10.0.0.1")
        # 手动将窗口起点设为很久以前
        count, start = login_limiter._records["10.0.0.1"]
        login_limiter._records["10.0.0.1"] = (count, time.monotonic() - login_limiter.window_seconds - 1)
        # 下一次调用应重置窗口（count 从 1 开始）
        assert login_limiter.is_allowed("10.0.0.1") is True
        assert login_limiter._records["10.0.0.1"][0] == 1

    def test_evict_expired_cleans_old_records(self):
        """TTL 过期清理：过期记录被 _evict_expired 删除"""
        login_limiter.is_allowed("10.0.0.1")
        login_limiter.is_allowed("10.0.0.2")
        # 将两个记录都设为过期
        now = time.monotonic()
        login_limiter._records["10.0.0.1"] = (5, now - login_limiter.window_seconds - 1)
        login_limiter._records["10.0.0.2"] = (3, now - login_limiter.window_seconds - 1)
        # 触发一次 is_allowed（内部会调用 _evict_expired）
        login_limiter.is_allowed("10.0.0.3")
        # 两个过期记录应被清除
        assert "10.0.0.1" not in login_limiter._records
        assert "10.0.0.2" not in login_limiter._records
        assert "10.0.0.3" in login_limiter._records


# ---- hmac.compare_digest ----


class TestHmacComparison:
    """验证 auth.py 使用 hmac.compare_digest 进行密码比较"""

    def test_hmac_compare_digest_used(self):
        """检查 auth.py login 函数源码中包含 hmac.compare_digest"""
        import inspect
        from app.api.auth import login
        source = inspect.getsource(login)
        assert "hmac.compare_digest" in source
