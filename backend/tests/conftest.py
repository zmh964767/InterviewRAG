"""测试共享 fixtures"""

import pytest
from fastapi.testclient import TestClient

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
