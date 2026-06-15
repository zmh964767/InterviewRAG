"""内存任务队列（单实例假设）

存储异步导入任务的状态信息。任务完成后保留 1 小时供前端查询。
"""

import logging
import threading
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal

logger = logging.getLogger(__name__)

TaskStatus = Literal["pending", "running", "done", "failed"]
TERMINAL_STATUSES = ("done", "failed")
_TERMINAL_TTL_SECONDS = 3600  # 1 hour


@dataclass
class Task:
    """单个导入任务的状态"""
    task_id: str
    status: str
    source_type: str
    source: str
    total: int = 0
    done: int = 0
    ingested: int = 0
    duplicates: int = 0
    errors: int = 0
    started_at: str = ""
    finished_at: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class TaskStore:
    """任务存储（进程内 dict）"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def _purge_expired(self) -> None:
        """清理已超时的终态任务（调用方需持有 _lock）"""
        now = datetime.now()
        expired = [
            tid for tid, task in self._tasks.items()
            if task.status in TERMINAL_STATUSES
            and task.finished_at
            and (now - datetime.fromisoformat(task.finished_at)).total_seconds() > _TERMINAL_TTL_SECONDS
        ]
        for tid in expired:
            del self._tasks[tid]
        if expired:
            logger.info(f"TaskStore: 清理 {len(expired)} 个过期任务")

    def create(self, source_type: str, source: str) -> Task:
        """创建任务，立即返回 task_id"""
        with self._lock:
            self._purge_expired()
            task = Task(
                task_id=str(uuid.uuid4()),
                status="pending",
                source_type=source_type,
                source=source,
                started_at=datetime.now().isoformat(),
            )
            self._tasks[task.task_id] = task
            return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            self._purge_expired()
            return self._tasks.get(task_id)

    def list_active(self) -> list[Task]:
        with self._lock:
            self._purge_expired()
            return [t for t in self._tasks.values() if t.status not in TERMINAL_STATUSES]

    def list_all(self) -> list[Task]:
        with self._lock:
            self._purge_expired()
            return list(self._tasks.values())

    def update(self, task_id: str, **kwargs) -> None:
        with self._lock:
            if task_id in self._tasks:
                for k, v in kwargs.items():
                    setattr(self._tasks[task_id], k, v)
                # 自动设置终态任务的 finished_at
                if "status" in kwargs and kwargs["status"] in TERMINAL_STATUSES:
                    if not self._tasks[task_id].finished_at:
                        self._tasks[task_id].finished_at = datetime.now().isoformat()


# 模块级单例
store = TaskStore()
