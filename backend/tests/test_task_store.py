"""TaskStore 单元测试"""

import pytest

from app.services.task_store import TERMINAL_STATUSES, Task, TaskStore


class TestTaskStore:
    def test_create_returns_task_with_id(self):
        store = TaskStore()
        task = store.create("md", "data/test.md")
        assert task.task_id
        assert task.status == "pending"
        assert task.source_type == "md"
        assert task.source == "data/test.md"
        assert task.started_at

    def test_get_returns_created(self):
        store = TaskStore()
        task = store.create("md", "x.md")
        got = store.get(task.task_id)
        assert got is task

    def test_get_missing_returns_none(self):
        store = TaskStore()
        assert store.get("nonexistent") is None

    def test_update_changes_fields(self):
        store = TaskStore()
        task = store.create("md", "x.md")
        store.update(task.task_id, status="running", done=5)
        assert store.get(task.task_id).status == "running"
        assert store.get(task.task_id).done == 5

    def test_update_nonexistent_is_noop(self):
        store = TaskStore()
        store.update("nope", status="done")  # 不抛异常
        assert store.get("nope") is None

    def test_list_active_excludes_terminal(self):
        store = TaskStore()
        t1 = store.create("md", "1.md")
        t2 = store.create("md", "2.md")
        t3 = store.create("md", "3.md")
        store.update(t2.task_id, status="done")
        store.update(t3.task_id, status="failed")

        active = store.list_active()
        assert len(active) == 1
        assert active[0].task_id == t1.task_id

    def test_to_dict_contains_all_fields(self):
        task = Task(
            task_id="t1", status="done", source_type="md", source="x.md",
            total=10, done=10, ingested=8, duplicates=2, errors=0,
            started_at="2026-01-01T00:00:00", finished_at="2026-01-01T00:01:00",
        )
        d = task.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "done"
        assert d["total"] == 10
        assert d["finished_at"] == "2026-01-01T00:01:00"

    def test_terminal_statuses(self):
        assert "done" in TERMINAL_STATUSES
        assert "failed" in TERMINAL_STATUSES
        assert "running" not in TERMINAL_STATUSES
        assert "pending" not in TERMINAL_STATUSES
