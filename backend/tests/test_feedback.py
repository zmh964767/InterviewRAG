"""测试用户反馈 API

公开端:
- POST /api/feedback — 提交反馈(覆盖)
管理端:
- GET  /api/admin/feedback — 列表(分页 + 筛选)
- GET  /api/admin/feedback/stats — 统计
"""

import pytest


def _admin_token(client) -> str:
    res = client.post("/api/auth/login", json={"password": "admin123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def _admin_headers(client) -> dict:
    return {"Authorization": f"Bearer {_admin_token(client)}"}


def _submit(client, **overrides) -> dict:
    """辅助:提交一条👍反馈"""
    body = {
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "rating": 1,
        "comment": None,
        "message_content": "测试回答内容",
        "message_role": "assistant",
    }
    body.update(overrides)
    return client.post("/api/feedback", json=body).json() if False else body


class TestSubmitFeedback:
    """公开端 POST /api/feedback"""

    def test_submit_feedback_positive(self, client):
        """👍 反馈 → 201 + {id, message_id}"""
        res = client.post(
            "/api/feedback",
            json={
                "message_id": "msg-pos-1",
                "conversation_id": "conv-1",
                "rating": 1,
                "comment": None,
                "message_content": "回答内容",
                "message_role": "assistant",
            },
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert "id" in data
        assert data["message_id"] == "msg-pos-1"

    def test_submit_feedback_negative_with_comment(self, client):
        """👎 + comment 持久化"""
        res = client.post(
            "/api/feedback",
            json={
                "message_id": "msg-neg-1",
                "conversation_id": "conv-1",
                "rating": -1,
                "comment": "答非所问",
                "message_content": "回答内容",
                "message_role": "assistant",
            },
        )
        assert res.status_code == 201
        # 用 admin GET 验证 comment 落库
        token = _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        get_res = client.get("/api/admin/feedback", headers=headers)
        assert get_res.status_code == 200
        items = get_res.json()["items"]
        neg = next(i for i in items if i["message_id"] == "msg-neg-1")
        assert neg["rating"] == -1
        assert neg["comment"] == "答非所问"

    def test_submit_feedback_invalid_rating(self, client):
        """rating=0 返 422(Literal 校验)"""
        res = client.post(
            "/api/feedback",
            json={
                "message_id": "msg-bad-rating",
                "conversation_id": "conv-1",
                "rating": 0,
                "comment": None,
                "message_content": "x",
                "message_role": "assistant",
            },
        )
        assert res.status_code == 422

    def test_submit_feedback_oversized_content(self, client):
        """message_content > 10KB 返 422"""
        big = "x" * 10_001
        res = client.post(
            "/api/feedback",
            json={
                "message_id": "msg-big",
                "conversation_id": "conv-1",
                "rating": 1,
                "comment": None,
                "message_content": big,
                "message_role": "assistant",
            },
        )
        assert res.status_code == 422

    def test_submit_feedback_replaces_existing(self, client):
        """同一 message_id 第二次提交 → 覆盖(用 get_feedback_by_message_id 验证)"""
        # 第一次:👍
        res1 = client.post(
            "/api/feedback",
            json={
                "message_id": "msg-replace",
                "conversation_id": "conv-1",
                "rating": 1,
                "comment": "first",
                "message_content": "answer",
                "message_role": "assistant",
            },
        )
        assert res1.status_code == 201

        # 第二次:👎 + 不同 comment
        res2 = client.post(
            "/api/feedback",
            json={
                "message_id": "msg-replace",
                "conversation_id": "conv-1",
                "rating": -1,
                "comment": "second",
                "message_content": "answer",
                "message_role": "assistant",
            },
        )
        assert res2.status_code == 201

        # 用 admin GET 验证
        headers = _admin_headers(client)
        items = client.get("/api/admin/feedback", headers=headers).json()["items"]
        replace_rows = [i for i in items if i["message_id"] == "msg-replace"]
        # 覆盖后只剩 1 条
        assert len(replace_rows) == 1
        assert replace_rows[0]["rating"] == -1
        assert replace_rows[0]["comment"] == "second"


class TestAdminGetFeedback:
    """管理端 GET /api/admin/feedback"""

    def test_admin_get_feedback_list(self, client):
        """GET 返 {items, total, page, size} 结构"""
        # 提交 3 条
        for i in range(3):
            client.post(
                "/api/feedback",
                json={
                    "message_id": f"m-{i}",
                    "conversation_id": "c",
                    "rating": 1,
                    "comment": None,
                    "message_content": f"content-{i}",
                    "message_role": "assistant",
                },
            )

        res = client.get("/api/admin/feedback", headers=_admin_headers(client))
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_admin_get_feedback_filter_by_rating(self, client):
        """rating=1 只返 👍"""
        client.post("/api/feedback", json={
            "message_id": "p1", "conversation_id": "c",
            "rating": 1, "comment": None, "message_content": "x", "message_role": "assistant",
        })
        client.post("/api/feedback", json={
            "message_id": "n1", "conversation_id": "c",
            "rating": -1, "comment": "bad", "message_content": "x", "message_role": "assistant",
        })
        client.post("/api/feedback", json={
            "message_id": "p2", "conversation_id": "c",
            "rating": 1, "comment": None, "message_content": "x", "message_role": "assistant",
        })

        res = client.get(
            "/api/admin/feedback",
            params={"rating": 1},
            headers=_admin_headers(client),
        )
        data = res.json()
        assert data["total"] == 2
        assert all(i["rating"] == 1 for i in data["items"])

    def test_admin_get_feedback_pagination(self, client):
        """page=2 返回不同结果(总 5 条,size=2)"""
        for i in range(5):
            client.post("/api/feedback", json={
                "message_id": f"pg-{i}",
                "conversation_id": "c",
                "rating": 1,
                "comment": None,
                "message_content": f"content {i}",
                "message_role": "assistant",
            })

        headers = _admin_headers(client)
        page1 = client.get("/api/admin/feedback", params={"page": 1, "size": 2}, headers=headers).json()
        page2 = client.get("/api/admin/feedback", params={"page": 2, "size": 2}, headers=headers).json()
        page3 = client.get("/api/admin/feedback", params={"page": 3, "size": 2}, headers=headers).json()

        assert page1["total"] == 5
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 2
        assert len(page3["items"]) == 1

        # 三页 message_id 无重叠
        ids1 = {i["message_id"] for i in page1["items"]}
        ids2 = {i["message_id"] for i in page2["items"]}
        ids3 = {i["message_id"] for i in page3["items"]}
        assert ids1.isdisjoint(ids2)
        assert ids2.isdisjoint(ids3)
        assert ids1.isdisjoint(ids3)


class TestAdminFeedbackStats:
    """管理端 GET /api/admin/feedback/stats"""

    def test_admin_get_feedback_stats(self, client):
        """3 👍 + 2 👎 → positive=3 negative=2 total=5 rate=0.4"""
        for i in range(3):
            client.post("/api/feedback", json={
                "message_id": f"sp-{i}",
                "conversation_id": "c",
                "rating": 1, "comment": None, "message_content": "x", "message_role": "assistant",
            })
        for i in range(2):
            client.post("/api/feedback", json={
                "message_id": f"sn-{i}",
                "conversation_id": "c",
                "rating": -1, "comment": None, "message_content": "x", "message_role": "assistant",
            })

        res = client.get("/api/admin/feedback/stats", headers=_admin_headers(client))
        assert res.status_code == 200
        data = res.json()
        assert data["positive"] == 3
        assert data["negative"] == 2
        assert data["total"] == 5
        assert data["rate"] == pytest.approx(0.4, abs=1e-6)

    def test_admin_get_feedback_stats_empty(self, client):
        """空表 → rate=0"""
        res = client.get("/api/admin/feedback/stats", headers=_admin_headers(client))
        data = res.json()
        assert data["positive"] == 0
        assert data["negative"] == 0
        assert data["total"] == 0
        assert data["rate"] == 0.0

    def test_admin_feedback_requires_auth(self, client):
        """无 token 返 401"""
        res = client.get("/api/admin/feedback")
        assert res.status_code == 401
        res2 = client.get("/api/admin/feedback/stats")
        assert res2.status_code == 401
