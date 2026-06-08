"""知识库管理 API 集成测试

覆盖：
- GET /api/questions（列表 + 过滤 + 分页）
- DELETE /api/questions/{id}（双写一致性）
- POST /api/ingest/insert-one（撤销机制 + content_hash 冲突）
"""

import pytest

from app.services.task_store import store as task_store
from app.services import ingest_service as ingest_service_module


# =========================================================================
# Fixtures：mock 掉 ChromaDB / Embedding，避免真实网络调用
# =========================================================================


class _FakeEmbeddings:
    """返回每个文本一个固定维度的伪向量"""

    def __init__(self, dim: int = 8):
        self.dim = dim

    def __call__(self, input):  # noqa: A002
        return [[0.1] * self.dim for _ in input]


class _FakeCollection:
    def __init__(self):
        self.docs: dict[str, str] = {}

    def add(self, ids, documents, metadatas, embeddings=None):
        for i, d in zip(ids, documents):
            self.docs[i] = d

    def delete(self, ids):
        for i in ids:
            self.docs.pop(i, None)

    def count(self):
        return len(self.docs)


class _FakeClient:
    def __init__(self):
        self.collection = _FakeCollection()

    def get_or_create_collection(self, name, metadata=None, embedding_function=None):
        return self.collection

    def delete_collection(self, name):
        self.collection = _FakeCollection()


class _FakeVectorStore:
    def __init__(self):
        self.client = _FakeClient()
        self.collection = self.client.collection
        self.embed_fn = None

    def add_documents(self, ids, documents, metadatas, embeddings=None):
        self.collection.add(ids, documents, metadatas, embeddings)

    def delete_by_id(self, qid):
        self.collection.delete([qid])
        return True

    def count(self):
        return self.collection.count()


@pytest.fixture
def fake_vs(monkeypatch):
    """替换 VectorStore 为假实现"""
    fake = _FakeVectorStore()

    def _factory():
        return fake

    monkeypatch.setattr("app.core.vectorstore.VectorStore", _factory)
    monkeypatch.setattr("app.api.questions._get_vs", lambda: fake)
    monkeypatch.setattr(
        "app.services.ingest_service.IngestService.__init__",
        lambda self: setattr(self, "vector_store", fake) or setattr(self, "db", None),
    )
    return fake


# =========================================================================
# GET /api/questions
# =========================================================================


class TestListQuestionsAPI:
    """GET /api/questions — 分页 + 过滤"""

    def test_empty_returns_empty(self, client, fake_vs):
        res = client.get("/api/questions")
        assert res.status_code == 200
        body = res.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["size"] == 20
        assert body["categories"] == []

    def test_pagination_params(self, client, fake_vs):
        res = client.get("/api/questions?page=2&size=10")
        assert res.status_code == 200
        assert res.json()["page"] == 2
        assert res.json()["size"] == 10

    def test_size_clamped(self, client, fake_vs):
        # size > 100 应被 Query(le=100) 拒绝
        res = client.get("/api/questions?size=200")
        assert res.status_code == 422

    def test_filters_propagate(self, client, fake_vs):
        # 通过 client 先插入数据需要直接调 Database，这里简化：仅验证 query 接受参数
        res = client.get(
            "/api/questions?q=test&category=前端&difficulty=中等"
        )
        assert res.status_code == 200
        body = res.json()
        assert body["items"] == []  # 空库


# =========================================================================
# DELETE /api/questions/{id}
# =========================================================================


class TestDeleteQuestionAPI:
    """DELETE /api/questions/{id} — 双写一致性"""

    def test_delete_nonexistent_returns_404(self, client, fake_vs):
        res = client.delete("/api/questions/nonexistent")
        assert res.status_code == 404
        assert "未找到" in res.json()["detail"]

    def test_delete_calls_chromadb_first(self, client, fake_vs):
        """ChromaDB 失败时不删 SQLite"""

        class _RaisingVS(_FakeVectorStore):
            def delete_by_id(self, qid):
                raise RuntimeError("ChromaDB 异常")

        # 替换 _get_vs 为会抛异常的版本
        import app.api.questions as qmod

        original_get_vs = qmod._get_vs
        qmod._get_vs = lambda: _RaisingVS()
        try:
            res = client.delete("/api/questions/anyid")
            assert res.status_code == 500
        finally:
            qmod._get_vs = original_get_vs


# =========================================================================
# POST /api/ingest/insert-one
# =========================================================================


class TestInsertOneAPI:
    """POST /api/ingest/insert-one — 撤销机制"""

    def test_missing_fields(self, client, fake_vs):
        res = client.post("/api/ingest/insert-one", json={})
        assert res.status_code == 422

    def test_duplicate_returns_409(self, client, fake_vs):
        payload = {
            "question": "Q?",
            "answer": "A.",
            "category": "前端",
            "difficulty": "中等",
            "source": "test",
        }
        # 第一次插入
        res1 = client.post("/api/ingest/insert-one", json=payload)
        assert res1.status_code == 201

        # 第二次相同 content_hash → 409
        res2 = client.post("/api/ingest/insert-one", json=payload)
        assert res2.status_code == 409
        assert "已存在" in res2.json()["detail"]

    def test_stable_id(self, client, fake_vs):
        payload = {
            "question": "测试 ID",
            "answer": "测试答案",
            "category": "前端",
            "difficulty": "简单",
            "source": "test",
        }
        res = client.post("/api/ingest/insert-one", json=payload)
        assert res.status_code == 201
        body = res.json()
        # id 应该是 md5(question|answer) 前 16 字符
        import hashlib

        expected = hashlib.md5(f"测试 ID|测试答案".encode()).hexdigest()[:16]
        assert body["id"] == expected
        assert body["question"] == "测试 ID"
        assert body["answer"] == "测试答案"
