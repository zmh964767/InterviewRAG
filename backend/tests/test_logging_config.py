"""structlog 配置 + Request ID 中间件单测

覆盖：
- structlog JSON 输出格式
- stdlib logger 通过 structlog 包装后也输出 JSON
- contextvars 中的 request_id 自动注入到日志
- Request ID 中间件：生成、传递、响应头
"""

import json

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import Response

from app.core.logging_config import setup_logging
from app.core.request_id_middleware import REQUEST_ID_HEADER, RequestIDMiddleware


# ─── structlog 配置测试 ──────────────────────────────────────────────────


class TestLoggingConfig:
    def test_setup_logging_runs_without_error(self):
        """setup_logging() 不抛异常"""
        setup_logging(json_output=True)

    def test_structlog_outputs_json(self, capsys):
        """structlog native logger 输出 JSON 格式"""
        setup_logging(json_output=True)
        log = structlog.get_logger("test")
        log.info("test_event", key="value")

        captured = capsys.readouterr()
        # stdout 或 stderr 都可能有输出
        output = captured.err or captured.out
        assert output.strip()
        data = json.loads(output.strip().split("\n")[-1])
        assert data["event"] == "test_event"
        assert data["key"] == "value"
        assert data["level"] == "info"
        assert "timestamp" in data

    def test_contextvars_injected(self, capsys):
        """contextvars 中的字段自动注入到日志"""
        setup_logging(json_output=True)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id="test-req-123")

        log = structlog.get_logger("test")
        log.info("context_test")

        captured = capsys.readouterr()
        output = captured.err or captured.out
        data = json.loads(output.strip().split("\n")[-1])
        assert data["request_id"] == "test-req-123"

        structlog.contextvars.clear_contextvars()


# ─── Request ID 中间件测试 ─────────────────────────────────────────────


class TestRequestIDMiddleware:
    def _make_app(self):
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        return app

    def test_auto_generates_request_id(self):
        """未传 X-Request-ID 时自动生成"""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert REQUEST_ID_HEADER in resp.headers
        # UUID 格式验证（8-4-4-4-12）
        rid = resp.headers[REQUEST_ID_HEADER]
        assert len(rid) == 36
        assert rid.count("-") == 4

    def test_passes_client_request_id(self):
        """客户端传入的 X-Request-ID 被透传"""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/test", headers={REQUEST_ID_HEADER: "my-custom-id"})
        assert resp.headers[REQUEST_ID_HEADER] == "my-custom-id"

    def test_request_id_in_response_header(self):
        """响应头始终包含 X-Request-ID"""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/test")
        assert REQUEST_ID_HEADER in resp.headers
