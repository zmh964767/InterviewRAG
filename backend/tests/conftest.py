"""测试共享 fixtures"""

import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.models.database import Database
import app.core.db as db_module
from app.api import ingest as ingest_mod

# CI 没有 .env 文件,确保 RAGService 初始化时不会因缺少 API key 崩溃
os.environ.setdefault("ZHIPU_API_KEY", "test-key-for-ci")

from app.main import app


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path):
    """每个测试使用独立临时 SQLite，防止测试间污染"""
    tmp_db = tmp_path / "test.db"
    original_db = db_module._db
    original_ingest = ingest_mod._ingest_service

    db_module._db = Database.__new__(Database)
    conn = sqlite3.connect(str(tmp_db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    db_module._db.conn = conn
    db_module._db._init_tables()

    ingest_mod._ingest_service = None  # 重置单例

    yield db_module._db

    conn.close()
    db_module._db = original_db
    ingest_mod._ingest_service = original_ingest


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
