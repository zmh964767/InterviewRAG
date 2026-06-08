# 知识库管理 UI — 实施计划

## 1. 实施顺序（4 阶段）

按依赖关系拆分为 4 个阶段，每阶段可独立验证：

| 阶段 | 内容 | 验证方式 | 依赖 |
|---|---|---|---|
| **Stage 1：后端基础** | 路径白名单 + Database/VectorStore 新增方法 | pytest 单测 | 无 |
| **Stage 2：后端 API** | 列表/删除/insert-one + 异步任务 + task 状态查询 | pytest 集成测 | Stage 1 |
| **Stage 3：前端基础** | Sidebar 路由切换 + /kb 页面骨架 + 表格/卡片 + 详情抽屉 + 删除流程 | 浏览器手动测 | Stage 2 |
| **Stage 4：导入 + 异步** | IngestModal 3 Tab + 任务轮询 + 撤销 Toast | 浏览器手动测 + e2e | Stage 3 |

---

## 2. Stage 1：后端基础（预计 1-2 小时）

### 2.1 创建 `backend/app/core/path_guard.py`

```python
"""服务端文件路径白名单校验

防止路径遍历攻击：限制所有 ingest 的服务端路径必须在 ./data 目录下。
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SAFE_DATA_DIR = Path("./data").resolve()


class PathGuardError(ValueError):
    """路径不安全"""


def validate_safe_path(rel_path: str) -> Path:
    """校验并返回安全的绝对路径"""
    if not rel_path:
        raise PathGuardError("路径不能为空")
    p = Path(rel_path)
    if p.is_absolute():
        raise PathGuardError("绝对路径被拒绝")
    parts = p.parts
    if ".." in parts:
        raise PathGuardError("包含 .. 的路径被拒绝")
    target = (SAFE_DATA_DIR / rel_path).resolve()
    if not str(target).startswith(str(SAFE_DATA_DIR) + "/") and target != SAFE_DATA_DIR:
        raise PathGuardError("路径逃逸到 data 目录外")
    if target.is_symlink():
        raise PathGuardError("符号链接被拒绝")
    return target
```

**修改**：[backend/app/services/ingest_service.py:29-32] — `ingest_md` 入口加 `validate_safe_path(file_path)` 调用；`ingest_pdf` 同理。

### 2.2 修改 [backend/app/models/database.py](backend/app/models/database.py)

新增 3 个方法：
- `delete_by_id(question_id: str) -> bool`
- `list_questions(filters: dict, page: int, size: int) -> tuple[list[dict], int]`
- `list_categories() -> list[str]`

**实现要点**：
- `list_questions` 用 `WHERE question LIKE ? OR answer LIKE ?` 做关键词搜索
- `list_questions` 用 `LIMIT ? OFFSET ?` 做分页
- `list_categories` 用 `SELECT DISTINCT category FROM questions WHERE category IS NOT NULL`
- 三个方法都用 `dict` row 工厂（已配置）

### 2.3 修改 [backend/app/core/vectorstore.py](backend/app/core/vectorstore.py)

新增 `delete_by_id(question_id: str) -> bool`：
```python
def delete_by_id(self, question_id: str) -> bool:
    """删除单条向量"""
    self.collection.delete(ids=[question_id])
    logger.info(f"已删除 ChromaDB 文档: {question_id}")
    return True
```

### 2.4 验证

```bash
cd backend
python -m pytest tests/test_path_guard.py -v   # 新增
python -m pytest tests/test_database.py -v      # 扩展已有
```

**预期**：所有用例通过。

---

## 3. Stage 2：后端 API（预计 2-3 小时）

### 3.1 修改 [backend/app/models/schemas.py](backend/app/models/schemas.py)

新增 3 个 schema：
- `QuestionListRequest`、`QuestionListResponse`
- `InsertOneRequest`、`InsertOneResponse`（复用 `Question`）
- `TaskStatusResponse`

### 3.2 创建 [backend/app/services/task_store.py](backend/app/services/task_store.py)

```python
"""内存任务队列（单实例假设）"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

logger = logging.getLogger(__name__)

TaskStatus = Literal["pending", "running", "done", "failed"]


@dataclass
class Task:
    task_id: str
    status: TaskStatus
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


class TaskStore:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    def create(self, source_type: str, source: str) -> Task:
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
        return [t for t in self._tasks.values() if t.status in ("pending", "running")]

    def update(self, task_id: str, **kwargs):
        if task_id in self._tasks:
            for k, v in kwargs.items():
                setattr(self._tasks[task_id], k, v)


# 模块级单例
store = TaskStore()
```

### 3.3 创建 [backend/app/api/questions.py](backend/app/api/questions.py)

```python
"""题目管理 API"""
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import QuestionListRequest, QuestionListResponse, Question
from app.models.database import Database
from app.core.vectorstore import VectorStore
from app.services.task_store import store as task_store  # 重用 store

router = APIRouter()
_db: Database | None = None
_vs: VectorStore | None = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def _get_vs() -> VectorStore:
    global _vs
    if _vs is None:
        _vs = VectorStore()
    return _vs


@router.get("/questions", response_model=QuestionListResponse)
async def list_questions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str = "",
    category: str = "",
    difficulty: str = "",
):
    db = _get_db()
    filters = {"q": q, "category": category, "difficulty": difficulty}
    items, total = db.list_questions(filters, page, size)
    categories = db.list_categories()
    return QuestionListResponse(
        items=items, total=total, page=page, size=size, categories=categories
    )


@router.delete("/questions/{question_id}")
async def delete_question(question_id: str):
    db = _get_db()
    vs = _get_vs()

    # 安全失败方向：先 ChromaDB 再 SQLite
    try:
        vs.delete_by_id(question_id)
    except Exception as e:
        raise HTTPException(500, f"ChromaDB 删除失败: {e}")

    if not db.delete_by_id(question_id):
        raise HTTPException(404, "题目不存在")

    return {"deleted": True, "id": question_id}
```

### 3.4 修改 [backend/app/api/ingest.py](backend/app/api/ingest.py)

**改造**：
- `POST /ingest` 和 `POST /ingest/upload` 改为立即返回 202 + task_id
- `POST /ingest/insert-one` 新增
- `GET /ingest/tasks/{task_id}` 新增
- `GET /ingest/tasks` 新增

**关键点**：用 `asyncio.create_task` 启动后台协程，串行执行（避免 Embedding API 限流）。

### 3.5 修改 [backend/app/main.py](backend/app/main.py)

注册新 router：
```python
from app.api import questions
app.include_router(questions.router, prefix="/api", tags=["questions"])
```

### 3.6 验证

```bash
cd backend
python -m pytest tests/test_questions.py -v      # 新增：列表/删除/insert-one
python -m pytest tests/test_task_store.py -v     # 新增：异步任务状态机
# 手动验证：启动 uvicorn，curl 测试 4 个新端点
```

**预期**：所有用例通过；手动 curl 返回正确数据。

---

## 4. Stage 3：前端基础（预计 3-4 小时）

### 4.1 修改 [frontend/lib/types.ts](frontend/lib/types.ts)

扩展：
```typescript
export interface Question {
  id: string
  question: string
  answer: string
  category: string
  difficulty: string
  source: string
  tags: string[]
  created_at: string
}

export interface QuestionListRequest {
  page?: number
  size?: number
  q?: string
  category?: string
  difficulty?: string
}

export interface QuestionListResponse {
  items: Question[]
  total: number
  page: number
  size: number
  categories: string[]
}

export type TaskStatus = 'pending' | 'running' | 'done' | 'failed'

export interface TaskStatusResponse {
  task_id: string
  status: TaskStatus
  source_type: string
  source: string
  total: number
  done: number
  ingested: number
  duplicates: number
  errors: number
  started_at: string
  finished_at: string | null
  error_message: string | null
}
```

### 4.2 扩展 [frontend/lib/api.ts](frontend/lib/api.ts)

新增 4 个函数：
- `listQuestions(request: QuestionListRequest): Promise<QuestionListResponse>`
- `deleteQuestion(id: string): Promise<void>`
- `insertOne(question: Partial<Question>): Promise<Question>`
- `getTaskStatus(taskId: string): Promise<TaskStatusResponse>`
- `listActiveTasks(): Promise<TaskStatusResponse[]>`

### 4.3 修改 [frontend/components/layout/Sidebar.tsx](frontend/components/layout/Sidebar.tsx)

**改动**：
- 第 25 行 `useState<Tab>` 改为由 `usePathname()` 决定
- 顶部 Tab `onClick` 改为 `router.push`
- 删除 `setActiveTab` state

### 4.4 创建 [frontend/app/kb/page.tsx](frontend/app/kb/page.tsx)

骨架：
```tsx
'use client'
import { Sidebar } from '@/components/layout/Sidebar'
import { useKnowledgeBase } from '@/hooks/useKnowledgeBase'

export default function KbPage() {
  const kb = useKnowledgeBase()
  return (
    <div className="flex h-screen">
      <Sidebar ... />
      <main className="flex-1 flex flex-col">
        <Toolbar ... />
        <QuestionTable ... />
      </main>
      {selectedId && <QuestionDetail ... />}
    </div>
  )
}
```

### 4.5 创建 [frontend/hooks/useKnowledgeBase.ts](frontend/hooks/useKnowledgeBase.ts)

**实现要点**：
- 内部 state：items/total/categories/filters/page/isLoading
- `useEffect` 监听 filters + page 变化，自动调用 listQuestions
- 搜索框 300ms debounce
- `refresh()` 重新拉取
- `removeItem(id)` 本地立刻移除（乐观更新），失败回滚

### 4.6 创建 [frontend/components/kb/](frontend/components/kb/) 下的组件

- `QuestionTable.tsx`：桌面端表格，按列宽定义列
- `QuestionCard.tsx`：<1024px 移动端卡片
- `QuestionDetail.tsx`：右侧抽屉，480-600px
- `DeleteConfirmDialog.tsx`：删除弹窗

### 4.7 验证

```bash
cd frontend
npm run dev   # 启动 Next.js
# 浏览器访问 http://localhost:3000/kb
# 测试：列表显示、过滤、详情抽屉、删除流程（含 5 秒撤销）
```

**预期**：所有交互正常，删除后 5 秒内可撤销，撤销后题目重新出现在列表里。

---

## 5. Stage 4：导入 + 异步（预计 2-3 小时）

### 5.1 创建 [frontend/hooks/useIngestTask.ts](frontend/hooks/useIngestTask.ts)

```typescript
export function useIngestTask() {
  const [task, setTask] = useState<TaskStatusResponse | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const start = useCallback((taskId: string) => {
    setIsPolling(true)
    const poll = async () => {
      try {
        const status = await getTaskStatus(taskId)
        setTask(status)
        if (status.status === 'done' || status.status === 'failed') {
          stop()
        }
      } catch (e) {
        // 404 = task 丢失
        stop()
      }
    }
    poll()
    intervalRef.current = setInterval(poll, 1000)
  }, [])

  const stop = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    setIsPolling(false)
  }, [])

  useEffect(() => () => stop(), [stop])
  return { task, isPolling, start, stop }
}
```

### 5.2 创建 [frontend/components/kb/IngestModal.tsx](frontend/components/kb/IngestModal.tsx)

**3 Tab**：
- Tab 1「上传文件」：`<input type="file" accept=".md,.pdf">` + 「开始导入」按钮
- Tab 2「URL」：`<input type="url">` + 「开始导入」按钮
- Tab 3「服务端路径」：`<input>` + 「开始导入」按钮（后端会做白名单校验）

**底部进度区**：用 `useIngestTask` 轮询，显示进度条 + 完成结果。

### 5.3 创建 [frontend/components/kb/UndoToast.tsx](frontend/components/kb/UndoToast.tsx)

**逻辑**：
- 5 秒倒计时（用 `setTimeout` 或纯 CSS 动画）
- 点「撤销」调用 `insertOne` 重新插入
- 倒计时结束自动隐藏
- 撤销失败时弹不同 Toast「撤销失败」

### 5.4 创建 [frontend/components/kb/ImportProgress.tsx](frontend/components/kb/ImportProgress.tsx)

显示任务进度条 + 完成结果（新增 X / 重复 Y / 失败 Z）。

### 5.5 验证

```bash
# 测试场景：
# 1. 上传一个 1MB 的 MD 文件
# 2. 模态框内看到进度条 0% → 100%
# 3. 完成后切到列表，看到新题
# 4. 删除一个题 → 5 秒内撤销 → 题目恢复
# 5. 关闭模态框后任务仍能在 Toast 看到
# 6. 故意输入 /etc/passwd 路径 → 弹「路径不安全」错误
```

**预期**：所有 6 个场景通过。

---

## 6. Review Gates（每个 Stage 结束前必做）

| Gate | 检查 |
|---|---|
| `trellis-before-dev` | 调取 `.trellis/spec/backend/` 和 `frontend/` 的规范 |
| `trellis-check` | 后端：lint + type + pytest；前端：tsc + next build |
| 类型一致性 | 前端 `Question` schema 必须和后端 `Question` schema 一致 |
| 集成测 | curl 跑通 4 个新端点，断言响应结构 |
| 浏览器手测 | Stage 3/4 必须浏览器手动验证 |

## 7. 验证命令清单

```bash
# 后端
cd backend
python -m pytest tests/ -v
python -m ruff check app/
python -m mypy app/

# 前端
cd frontend
npm run lint
npx tsc --noEmit
npm run build
npm run dev  # 手动浏览器测试
```

## 8. 回滚点

| 阶段 | 回滚操作 |
|---|---|
| Stage 1 | 删除 `path_guard.py`，还原 `ingest_service.py` |
| Stage 2 | 删除 `task_store.py` + `questions.py`，还原 `ingest.py`（同步），移除 `main.py` 注册 |
| Stage 3 | 删除 `kb/page.tsx` + 整个 `components/kb/` 目录，移除 `Sidebar.tsx` 改造 |
| Stage 4 | 已经在 Stage 3 之上，恢复 Stage 3 即可 |

## 9. 风险点提醒

- **删除一致性**：必须先 ChromaDB 再 SQLite（design §3.1）
- **路径遍历**：所有 `ingest_*` 入口都过 `path_guard`
- **异步任务**：单实例假设，进程重启任务丢失（用户需重提）
- **前端缓存**：删除后 5 秒撤销窗口依赖前端缓存题面，不要清 localStorage 否则撤销会失败

## 10. 拆分建议

如果时间紧，可拆为 3 个**子任务**（独立归档）：
1. **kb-01-backend**：Stage 1+2
2. **kb-02-frontend-list**：Stage 3（不含导入）
3. **kb-03-frontend-import**：Stage 4

子任务用 `task.py add-subtask <parent> <child>` 链接，独立可验证。
