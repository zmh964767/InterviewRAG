"""测试共享 fixtures"""

import os
import pytest
from fastapi.testclient import TestClient

# CI 没有 .env 文件,确保 RAGService 初始化时不会因缺少 API key 崩溃
os.environ.setdefault("ZHIPU_API_KEY", "test-key-for-ci")

from app.main import app


@pytest.fixture
def client():
    """FastAPI 测试客户端"""
    return TestClient(app)


@pytest.fixture
def sample_question():
    """示例问题"""
    return "什么是Transformer"


@pytest.fixture
def sample_messages():
    """示例对话历史"""
    return [
        {"role": "user", "content": "什么是RAG？"},
        {"role": "assistant", "content": "RAG是检索增强生成的缩写。"},
    ]
