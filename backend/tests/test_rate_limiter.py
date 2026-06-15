"""共享限流模块单测

覆盖 PerIPRateLimiter:
- 首次请求允许
- 达到上限后拒绝
- reset 清除记录
- 窗口过期后重置
- 不同 IP 独立限流
- TTL 过期清理（_evict_expired）

覆盖 get_client_ip:
- 无 XFF 时返回 direct IP
- trusted_proxies 为空时忽略 XFF
- trusted_proxies 匹配时读取 XFF
- XFF 多个值时取第一个
- request.client 为 None 时返回 "unknown"
"""

import time
from unittest.mock import MagicMock

import pytest

from app.core.rate_limiter import PerIPRateLimiter, get_client_ip


# ---- PerIPRateLimiter ----


class TestPerIPRateLimiter:
    """PerIPRateLimiter 核心行为"""

    def test_first_request_allowed(self):
        limiter = PerIPRateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed("10.0.0.1") is True

    def test_within_limit_allowed(self):
        limiter = PerIPRateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.is_allowed("10.0.0.1") is True

    def test_exceed_limit_blocked(self):
        limiter = PerIPRateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1") is False

    def test_reset_clears_record(self):
        limiter = PerIPRateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1") is False
        limiter.reset("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1") is True

    def test_reset_nonexistent_ip_no_error(self):
        limiter = PerIPRateLimiter(max_requests=3, window_seconds=60)
        limiter.reset("9.9.9.9")  # should not raise

    def test_window_expiry_resets_count(self):
        limiter = PerIPRateLimiter(max_requests=3, window_seconds=60)
        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.1")
        # Manually set window_start to past
        limiter._records["10.0.0.1"] = (2, time.monotonic() - 61)
        # Next call should reset window
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter._records["10.0.0.1"][0] == 1

    def test_different_ips_independent(self):
        limiter = PerIPRateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            limiter.is_allowed("1.1.1.1")
        assert limiter.is_allowed("1.1.1.1") is False
        assert limiter.is_allowed("2.2.2.2") is True

    def test_evict_expired_removes_old_entries(self):
        limiter = PerIPRateLimiter(max_requests=5, window_seconds=60)
        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.2")
        # Mark both as expired
        now = time.monotonic()
        limiter._records["10.0.0.1"] = (5, now - 61)
        limiter._records["10.0.0.2"] = (3, now - 61)
        # Trigger eviction via a new is_allowed call
        limiter.is_allowed("10.0.0.3")
        assert "10.0.0.1" not in limiter._records
        assert "10.0.0.2" not in limiter._records
        assert "10.0.0.3" in limiter._records

    def test_evict_expired_keeps_active_entries(self):
        limiter = PerIPRateLimiter(max_requests=5, window_seconds=60)
        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.2")
        # Only mark .1 as expired, .2 stays active
        now = time.monotonic()
        limiter._records["10.0.0.1"] = (5, now - 61)
        # .2 is still within window (just created)
        limiter.is_allowed("10.0.0.3")
        assert "10.0.0.1" not in limiter._records
        assert "10.0.0.2" in limiter._records

    def test_max_requests_equals_one(self):
        """边界：max_requests=1 时第 2 次即被限流"""
        limiter = PerIPRateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is False

    def test_concurrent_is_allowed(self):
        """多线程并发调用 is_allowed 不崩溃、不超发"""
        import threading

        limiter = PerIPRateLimiter(max_requests=100, window_seconds=60)
        results = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            for _ in range(20):
                results.append(limiter.is_allowed("10.0.0.1"))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed = sum(results)
        assert allowed <= 100  # must not exceed max_requests
        assert allowed >= 1    # at least the first batch gets through


# ---- get_client_ip ----


class TestGetClientIp:
    """get_client_ip 各场景"""

    def _make_request(self, client_host=None, xff_header=None):
        """构造 mock Request"""
        req = MagicMock()
        if client_host is None:
            req.client = None
        else:
            req.client.host = client_host
        headers = {}
        if xff_header is not None:
            headers["X-Forwarded-For"] = xff_header
        req.headers = headers
        return req

    def test_returns_direct_ip_when_no_xff(self):
        req = self._make_request("192.168.1.1")
        assert get_client_ip(req, trusted_proxies=[]) == "192.168.1.1"

    def test_xff_ignored_when_trusted_proxies_empty(self):
        req = self._make_request("1.2.3.4", "9.8.7.6")
        assert get_client_ip(req, trusted_proxies=[]) == "1.2.3.4"

    def test_xff_ignored_when_direct_ip_not_in_trusted(self):
        req = self._make_request("5.5.5.5", "9.8.7.6")
        assert get_client_ip(req, trusted_proxies=["127.0.0.1"]) == "5.5.5.5"

    def test_xff_read_when_direct_ip_is_trusted(self):
        req = self._make_request("127.0.0.1", "9.8.7.6, 10.0.0.1")
        assert get_client_ip(req, trusted_proxies=["127.0.0.1"]) == "9.8.7.6"

    def test_xff_first_value_with_spaces(self):
        req = self._make_request("10.0.0.1", "  192.168.1.1 , 10.0.0.1  ")
        assert get_client_ip(req, trusted_proxies=["10.0.0.1"]) == "192.168.1.1"

    def test_no_client_returns_unknown(self):
        req = self._make_request(None)
        assert get_client_ip(req, trusted_proxies=[]) == "unknown"

    def test_no_client_with_xff_and_matching_trusted(self):
        """client=None → direct_ip="unknown"，如果 "unknown" 在信任列表则读 XFF"""
        req = self._make_request(None, "1.2.3.4")
        assert get_client_ip(req, trusted_proxies=["unknown"]) == "1.2.3.4"

    def test_xff_empty_string_falls_back_to_direct(self):
        """XFF 头存在但为空时返回 direct IP（空字串为 falsy）"""
        req = self._make_request("127.0.0.1", "")
        assert get_client_ip(req, trusted_proxies=["127.0.0.1"]) == "127.0.0.1"

    def test_xff_single_value(self):
        req = self._make_request("127.0.0.1", "3.3.3.3")
        assert get_client_ip(req, trusted_proxies=["127.0.0.1"]) == "3.3.3.3"

    def test_multiple_trusted_proxies(self):
        """多个信任代理 IP，匹配其中任何一个都能读 XFF"""
        trusted = ["127.0.0.1", "10.0.0.1"]
        req = self._make_request("10.0.0.1", "7.7.7.7")
        assert get_client_ip(req, trusted_proxies=trusted) == "7.7.7.7"
