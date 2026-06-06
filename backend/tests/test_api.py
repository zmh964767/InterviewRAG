"""API 端点测试（Mock 外部服务，快速运行）"""

import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    """健康检查接口"""

    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "vector_count" in data

    def test_health_vector_count_is_int(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert isinstance(data["vector_count"], int)


class TestStatsEndpoint:
    """统计接口"""

    def test_stats_returns_structure(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_questions" in data
        assert "categories" in data
        assert isinstance(data["categories"], dict)


class TestQueryValidation:
    """问答接口参数校验"""

    def test_query_missing_question(self, client):
        response = client.post("/api/query", json={})
        assert response.status_code == 422

    def test_query_empty_question(self, client):
        response = client.post("/api/query", json={"question": ""})
        assert response.status_code == 422

    def test_query_requires_question_field(self, client):
        response = client.post("/api/query", json={"stream": False})
        assert response.status_code == 422


class TestQueryWithMock:
    """问答接口（Mock LLM，快速验证流程）"""

    @patch("app.services.rag_service.RAGService.query")
    def test_query_non_stream(self, mock_query, client):
        mock_query.return_value = {
            "answer": "测试回答内容",
            "sources": [
                {"id": "test-1", "question": "测试题目", "answer": "测试答案", "score": 0.9, "category": "LLM"}
            ],
        }
        response = client.post(
            "/api/query",
            json={"question": "测试问题", "stream": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "测试回答内容"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["question_text"] == "测试题目"

    @patch("app.services.rag_service.RAGService.query")
    def test_query_with_history(self, mock_query, client):
        mock_query.return_value = {"answer": "回答", "sources": []}
        history = [
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
        ]
        response = client.post(
            "/api/query",
            json={"question": "问题2", "chat_history": history, "stream": False},
        )
        assert response.status_code == 200
        # 验证 history 被传递给 RAG service
        call_args = mock_query.call_args
        assert call_args.kwargs["chat_history"] == history

    @patch("app.services.rag_service.RAGService.query")
    def test_query_conversation_id(self, mock_query, client):
        mock_query.return_value = {"answer": "回答", "sources": []}
        response = client.post(
            "/api/query",
            json={"question": "问题", "conversation_id": "test-conv-123", "stream": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == "test-conv-123"

    @patch("app.services.rag_service.RAGService.query")
    def test_query_generates_conversation_id(self, mock_query, client):
        mock_query.return_value = {"answer": "回答", "sources": []}
        response = client.post(
            "/api/query",
            json={"question": "问题", "stream": False},
        )
        data = response.json()
        assert data["conversation_id"] is not None
        assert len(data["conversation_id"]) > 0
