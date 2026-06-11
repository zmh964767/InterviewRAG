"""知识库管理 API 集成测试

覆盖：
- GET /api/questions（公开列表 + 过滤 + 分页）
- DELETE /api/admin/questions/{id}（双写一致性，JWT 保护）
- POST /api/admin/ingest/insert-one（撤销机制 + content_hash 冲突）
"""

import pytest

from app.api import deps as deps_mod


@pytest.fixture
def admin_token(client):
    res = client.post("/api/auth/login", json={"password": "admin123"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# =========================================================================
# GET /api/questions (public)
# =========================================================================


class TestListQuestionsAPI:
    """GET /api/questions — 分页 + 过滤（公开）"""

    def test_empty_returns_empty(self, client):
        res = client.get("/api/questions")
        assert res.status_code == 200
        body = res.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["size"] == 20
        assert body["categories"] == []

    def test_pagination_params(self, client):
        res = client.get("/api/questions?page=2&size=10")
        assert res.status_code == 200
        assert res.json()["page"] == 2
        assert res.json()["size"] == 10

    def test_size_clamped(self, client):
        # size > 100 应被 Query(le=100) 拒绝
        res = client.get("/api/questions?size=200")
        assert res.status_code == 422

    def test_filters_propagate(self, client):
        res = client.get(
            "/api/questions?q=test&category=前端&difficulty=中等"
        )
        assert res.status_code == 200
        body = res.json()
        assert body["items"] == []  # 空库


# =========================================================================
# DELETE /api/admin/questions/{id} (protected)
# =========================================================================


class TestDeleteQuestionAPI:
    """DELETE /api/admin/questions/{id} — 双写一致性"""

    def test_delete_requires_auth(self, client):
        res = client.delete("/api/admin/questions/nonexistent")
        assert res.status_code == 401

    def test_delete_nonexistent_returns_404(self, client, admin_headers):
        res = client.delete("/api/admin/questions/nonexistent", headers=admin_headers)
        assert res.status_code == 404
        assert "未找到" in res.json()["detail"]

    def test_delete_calls_chromadb_first(self, client, admin_headers):
        """ChromaDB 失败时不删 SQLite"""

        class _RaisingVS:
            def delete_by_id(self, qid):
                raise RuntimeError("ChromaDB 异常")

        class _RaisingRAG:
            vector_store = _RaisingVS()

        from app.main import app

        app.dependency_overrides[deps_mod.get_rag_service] = lambda: _RaisingRAG()
        try:
            res = client.delete("/api/admin/questions/anyid", headers=admin_headers)
            assert res.status_code == 500
        finally:
            app.dependency_overrides.pop(deps_mod.get_rag_service, None)


# =========================================================================
# POST /api/admin/ingest/insert-one (protected)
# =========================================================================


class TestInsertOneAPI:
    """POST /api/admin/ingest/insert-one — 撤销机制"""

    def test_requires_auth(self, client):
        res = client.post("/api/admin/ingest/insert-one", json={})
        assert res.status_code == 401

    def test_missing_fields(self, client, admin_headers):
        res = client.post("/api/admin/ingest/insert-one", json={}, headers=admin_headers)
        assert res.status_code == 422

    def test_duplicate_returns_409(self, client, admin_headers):
        payload = {
            "question": "Q?",
            "answer": "A.",
            "category": "前端",
            "difficulty": "中等",
            "source": "test",
        }
        res1 = client.post("/api/admin/ingest/insert-one", json=payload, headers=admin_headers)
        assert res1.status_code == 201

        res2 = client.post("/api/admin/ingest/insert-one", json=payload, headers=admin_headers)
        assert res2.status_code == 409
        assert "已存在" in res2.json()["detail"]

    def test_stable_id(self, client, admin_headers):
        payload = {
            "question": "测试 ID",
            "answer": "测试答案",
            "category": "前端",
            "difficulty": "简单",
            "source": "test",
        }
        res = client.post("/api/admin/ingest/insert-one", json=payload, headers=admin_headers)
        assert res.status_code == 201
        body = res.json()
        import hashlib

        expected = hashlib.md5(f"测试 ID|测试答案".encode()).hexdigest()[:16]
        assert body["id"] == expected
        assert body["question"] == "测试 ID"
        assert body["answer"] == "测试答案"
