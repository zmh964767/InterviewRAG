"""Database 新增方法测试（delete_by_id / list_questions / list_categories）"""

import pytest

from app.models.database import Database


@pytest.fixture
def db(tmp_path, monkeypatch):
    """用临时目录覆盖数据库路径"""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("app.models.database.get_settings", lambda: type("S", (), {
        "sqlite_db_path": str(db_file),
    })())
    return Database()


def _make_q(qid: str, question: str, answer: str, category: str = "前端", difficulty: str = "中等", source: str = "x.md", tags: list[str] | None = None):
    return {
        "id": qid,
        "question": question,
        "answer": answer,
        "category": category,
        "difficulty": difficulty,
        "source": source,
        "tags": tags or [],
    }


class TestDeleteById:
    def test_deletes_existing(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1"))
        assert db.delete_by_id("q1") is True
        assert db.get_question_by_id("q1") is None

    def test_nonexistent_returns_false(self, db):
        assert db.delete_by_id("notexist") is False

    def test_one_of_many(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1"))
        db.insert_question(_make_q("q2", "Q2", "A2"))
        db.delete_by_id("q1")
        assert db.get_question_by_id("q1") is None
        assert db.get_question_by_id("q2") is not None


class TestListQuestions:
    def test_empty(self, db):
        items, total = db.list_questions({}, page=1, size=20)
        assert items == []
        assert total == 0

    def test_basic_pagination(self, db):
        for i in range(5):
            db.insert_question(_make_q(f"q{i}", f"Q{i}", f"A{i}"))

        items, total = db.list_questions({}, page=1, size=3)
        assert total == 5
        assert len(items) == 3

        items, total = db.list_questions({}, page=2, size=3)
        assert total == 5
        assert len(items) == 2

    def test_keyword_search_in_question(self, db):
        db.insert_question(_make_q("q1", "Python 装饰器", "answer"))
        db.insert_question(_make_q("q2", "Java 多线程", "answer"))
        items, total = db.list_questions({"q": "Python"}, page=1, size=20)
        assert total == 1
        assert items[0]["id"] == "q1"

    def test_keyword_search_in_answer(self, db):
        db.insert_question(_make_q("q1", "question", "包含 Python 的答案"))
        db.insert_question(_make_q("q2", "question", "不相关的答案"))
        items, total = db.list_questions({"q": "Python"}, page=1, size=20)
        assert total == 1
        assert items[0]["id"] == "q1"

    def test_category_filter(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1", category="前端"))
        db.insert_question(_make_q("q2", "Q2", "A2", category="算法"))
        items, total = db.list_questions({"category": "前端"}, page=1, size=20)
        assert total == 1
        assert items[0]["category"] == "前端"

    def test_difficulty_filter(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1", difficulty="简单"))
        db.insert_question(_make_q("q2", "Q2", "A2", difficulty="困难"))
        items, total = db.list_questions({"difficulty": "困难"}, page=1, size=20)
        assert total == 1
        assert items[0]["difficulty"] == "困难"

    def test_combined_filters(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1", category="前端", difficulty="简单"))
        db.insert_question(_make_q("q2", "Q2", "A2", category="前端", difficulty="困难"))
        db.insert_question(_make_q("q3", "Q3", "A3", category="算法", difficulty="简单"))
        items, total = db.list_questions(
            {"category": "前端", "difficulty": "简单"},
            page=1, size=20,
        )
        assert total == 1
        assert items[0]["id"] == "q1"


class TestRowToDict:
    """tags 字段 JSON 字符串 → list 转换（regression: Pydantic ValidationError）"""

    def test_tags_parsed_as_list_via_list_questions(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1", tags=["LLM", "Transformer"]))
        items, _ = db.list_questions({}, page=1, size=20)
        assert isinstance(items[0]["tags"], list)
        assert items[0]["tags"] == ["LLM", "Transformer"]

    def test_tags_parsed_as_list_via_get_question_by_id(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1", tags=["RAG"]))
        row = db.get_question_by_id("q1")
        assert isinstance(row["tags"], list)
        assert row["tags"] == ["RAG"]

    def test_tags_empty_list(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1", tags=[]))
        items, _ = db.list_questions({}, page=1, size=20)
        assert items[0]["tags"] == []

    def test_tags_default_empty(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1"))
        items, _ = db.list_questions({}, page=1, size=20)
        assert isinstance(items[0]["tags"], list)
        assert items[0]["tags"] == []


class TestListCategories:
    def test_empty(self, db):
        assert db.list_categories() == []

    def test_dedup_and_sort(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1", category="算法"))
        db.insert_question(_make_q("q2", "Q2", "A2", category="前端"))
        db.insert_question(_make_q("q3", "Q3", "A3", category="算法"))
        cats = db.list_categories()
        assert cats == ["前端", "算法"]  # 字母序

    def test_excludes_empty(self, db):
        # 手动插入空分类
        db.insert_question(_make_q("q1", "Q1", "A1", category=""))
        db.insert_question(_make_q("q2", "Q2", "A2", category="前端"))
        cats = db.list_categories()
        assert "" not in cats
        assert "前端" in cats


class TestBatchDelete:
    def test_batch_delete_basic(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1"))
        db.insert_question(_make_q("q2", "Q2", "A2"))
        db.insert_question(_make_q("q3", "Q3", "A3"))
        deleted = db.batch_delete(["q1", "q2"])
        assert deleted == 2
        assert db.get_question_by_id("q1") is None
        assert db.get_question_by_id("q2") is None
        assert db.get_question_by_id("q3") is not None

    def test_batch_delete_nonexistent(self, db):
        deleted = db.batch_delete(["notexist1", "notexist2"])
        assert deleted == 0

    def test_batch_delete_mixed(self, db):
        db.insert_question(_make_q("q1", "Q1", "A1"))
        db.insert_question(_make_q("q2", "Q2", "A2"))
        deleted = db.batch_delete(["q1", "notexist"])
        assert deleted == 1
        assert db.get_question_by_id("q1") is None
        assert db.get_question_by_id("q2") is not None

    def test_batch_delete_empty_list(self, db):
        deleted = db.batch_delete([])
        assert deleted == 0
