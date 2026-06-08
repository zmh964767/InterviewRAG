"""内存任务队列（单实例假设）

存储异步导入任务的状态信息。任务完成后保留 1 小时供前端查询。
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal

logger = logging.getLogger(__name__)

TaskStatus = Literal["pending", "running", "done", "failed"]
TERMINAL_STATUSES = ("done", "failed")


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
        self._lock = asyncio.Lock()

    def create(self, source_type: str, source: str) -> Task:
        """创建任务，立即返回 task_id"""
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
        return self._tasks.get(task_id)

    def list_active(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status not in TERMINAL_STATUSES]

    def list_all(self) -> list[Task]:
        return list(self._tasks.values())

    def update(self, task_id: str, **kwargs) -> None:
        if task_id in self._tasks:
            for k, v in kwargs.items():
                setattr(self._tasks[task_id], k, v)


# 模块级单例
store = TaskStore()
