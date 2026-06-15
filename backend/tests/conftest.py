"""测试共享 fixtures"""

import os
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from app.models.database import Database
import app.core.db as db_module
from app.api import deps as deps_mod
from app.api import ingest as ingest_mod
from app.api import admin_ingest as admin_ingest_mod

# CI 没有 .env 文件,确保 RAGService 初始化时不会因缺少 API key 崩溃
os.environ.setdefault("ZHIPU_API_KEY", "test-key-for-ci")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")


class _FakeCollection:
    """内存 ChromaDB 替身"""

    def __init__(self):
        self.docs: dict[str, str] = {}

    def add(self, ids, documents, metadatas=None, embeddings=None):
        for i, d in zip(ids, documents):
            self.docs[i] = d

    def delete(self, ids):
        for i in ids:
            self.docs.pop(i, None)

    def count(self):
        return len(self.docs)


class _FakeVectorStore:
    def __init__(self, *args, **kwargs):
        self.collection = _FakeCollection()

    def add_documents(self, ids, documents, metadatas, embeddings=None):
        self.collection.add(ids, documents, metadatas, embeddings)

    def delete_by_id(self, qid):
        self.collection.delete([qid])
        return True

    def count(self):
        return self.collection.count()

    def get_all(self):
        return {"documents": [], "metadatas": []}

    def query(self, *args, **kwargs):
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}


class _FakeRAGService:
    """最小化 RAGService 替身，只实现 health 用到的属性"""

    def __init__(self):
        self.vector_store = _FakeVectorStore()

        class _FakeLLM:
            def check_health(self_):
                return "ok"

        self.llm_service = _FakeLLM()


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path):
    """每个测试使用独立临时 SQLite，防止测试间污染"""
    tmp_db = tmp_path / "test.db"
    original_db = db_module._db
    original_ingest = ingest_mod._ingest_service
    original_admin_ingest = admin_ingest_mod._ingest_service

    db = Database.__new__(Database)
    conn = sqlite3.connect(str(tmp_db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    db.conn = conn
    db._write_lock = threading.Lock()
    db._init_tables()
    db_module.set_db(db)

    ingest_mod._ingest_service = None
    admin_ingest_mod._ingest_service = None  # 重置单例

    yield db

    conn.close()
    db_module._db = original_db
    ingest_mod._ingest_service = original_ingest
    admin_ingest_mod._ingest_service = original_admin_ingest


@pytest.fixture
def client(monkeypatch, fake_rag):
    """FastAPI 测试客户端

    1. monkeypatch RAGService.__init__ 让 lifespan 不做真实网络调用
    2. dependency_overrides 让所有 Depends(get_rag_service) 返回假实例
    3. TestClient(app) 自动触发 lifespan → app.state.db / app.state.rag 初始化
    """
    from app.main import app
    from app.services import rag_service as rag_mod

    # 替换 RAGService.__init__，让 lifespan 里的 RAGService() 不走真实初始化
    monkeypatch.setattr(rag_mod.RAGService, "__init__", _FakeRAGService.__init__)

    # 覆盖依赖注入：路由拿到的是 fake_rag 实例
    app.dependency_overrides[deps_mod.get_rag_service] = lambda: fake_rag

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture
def fake_rag():
    """可被测试直接操作的 FakeRAGService 实例（query 等方法可在测试里覆盖）"""
    return _FakeRAGService()


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
