"""query 端点限流集成测试

覆盖：
- 正常请求通过
- 超限返回 429
"""

import pytest
from unittest.mock import AsyncMock

import app.api.query as query_mod


@pytest.fixture(autouse=True)
def _reset_query_limiter():
    """每个测试前重置 query 限流器全局实例"""
    original = query_mod._query_limiter
    query_mod._query_limiter = None
    yield
    query_mod._query_limiter = original


@pytest.fixture
def _low_rate_limit(monkeypatch):
    """将 query 限流设为 3 次/分钟，方便测试"""
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("QUERY_RATE_LIMIT_PER_MIN", "3")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("QUERY_RATE_LIMIT_PER_MIN", raising=False)
    get_settings.cache_clear()


class TestQueryRateLimit:
    """query 端点 per-IP 限流"""

    def test_normal_request_passes(self, client, fake_rag):
        """正常请求不受限流影响"""
        fake_rag.query = AsyncMock(return_value={"answer": "ok", "sources": []})
        res = client.post("/api/query", json={"question": "test", "stream": False})
        assert res.status_code == 200

    def test_returns_429_when_exceeded(self, client, fake_rag, _low_rate_limit):
        """超过限额后返回 429"""
        fake_rag.query = AsyncMock(return_value={"answer": "ok", "sources": []})
        for _ in range(3):
            res = client.post("/api/query", json={"question": "test", "stream": False})
            assert res.status_code == 200
        # 4th request should be rate limited
        res = client.post("/api/query", json={"question": "test", "stream": False})
        assert res.status_code == 429
        assert "频繁" in res.json()["detail"]
