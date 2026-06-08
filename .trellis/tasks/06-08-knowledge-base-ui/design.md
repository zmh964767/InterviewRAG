# 知识库管理 UI — 技术设计

## 1. 架构与边界

### 1.1 模块划分

```
backend/
├── app/
│   ├── api/
│   │   ├── questions.py     # 新增：GET 列表 / DELETE 单条
│   │   └── ingest.py        # 改造：upload 改异步；新增 insert-one；新增 task 状态查询
│   ├── services/
│   │   ├── task_store.py    # 新增：内存任务队列（dict[task_id, Task]）
│   │   └── ingest_service.py  # 微调：拆出 _run_ingest_pipeline 供异步调用
│   ├── core/
│   │   └── vectorstore.py   # 新增：delete_by_id
│   ├── models/
│   │   ├── database.py      # 新增：delete_by_id / list_questions / list_categories
│   │   └── schemas.py       # 新增：QuestionListResponse / InsertOneRequest / TaskStatusResponse
│   ├── core/
│   │   └── path_guard.py    # 新增：服务端路径白名单校验
│   └── main.py              # 注册新 router
frontend/
├── app/
│   ├── layout.tsx           # 保持不变
│   ├── page.tsx             # 保持不变
│   └── kb/
│       └── page.tsx         # 新增：知识库管理全屏页
├── components/
│   ├── layout/
│   │   └── Sidebar.tsx      # 改造：Tab 改路由切换（activeTab 由 usePathname 决定）
│   └── kb/
│       ├── QuestionTable.tsx     # 新增：桌面端表格视图
│       ├── QuestionCard.tsx      # 新增：移动端卡片视图
│       ├── QuestionDetail.tsx    # 新增：详情抽屉
│       ├── IngestModal.tsx       # 新增：导入模态框（3 Tab）
│       ├── DeleteConfirmDialog.tsx  # 新增：删除二次确认弹窗
│       ├── UndoToast.tsx         # 新增：撤销 Toast（5 秒倒计时）
│       └── ImportProgress.tsx    # 新增：导入进度显示
├── hooks/
│   ├── useKnowledgeBase.ts  # 新增：列表/搜索/分页状态管理
│   └── useIngestTask.ts     # 新增：任务状态轮询
└── lib/
    ├── api.ts               # 扩展：listQuestions/deleteQuestion/insertOne/getTask
    └── types.ts             # 扩展：Question / QuestionList / TaskStatus
```

### 1.2 边界与责任

| 层 | 职责 | 不做 |
|---|---|---|
| API（router） | 协议层：解析参数、调用 service、返回 schema | 业务逻辑、SQL/向量操作 |
| Service | 业务编排：双写一致性、异步任务状态推进 | HTTP 细节 |
| Database / VectorStore | 物理存储：SQLite / ChromaDB | 业务规则、跨存储一致性 |
| Frontend Hook | UI 状态：列表缓存、轮询计时器、撤销窗口 | 直接调 fetch |
| Frontend Component | 渲染：表格/卡片/抽屉/Toast | 状态管理、API 调用 |

## 2. 数据流与契约

### 2.1 新增/改造的 API 端点

#### 2.1.1 列表查询
```http
GET /api/questions?page=1&size=20&q=keyword&category=前端&difficulty=中等
```
**Request**（Pydantic）：`QuestionListRequest`
- `page: int = 1`（1-based）
- `size: int = 20`（max 100，clamp）
- `q: str = ""`（题面+答案 LIKE 关键词）
- `category: str = ""`（精确匹配）
- `difficulty: str = ""`（精确匹配）

**Response**（`QuestionListResponse`）：
```json
{
  "items": [
    {
      "id": "a3f2b1c4d5e6f7g8",
      "question": "...",
      "answer": "...",
      "category": "前端",
      "difficulty": "中等",
      "source": "questions.md",
      "tags": ["前端"],
      "created_at": "2026-06-01T12:34:56"
    }
  ],
  "total": 142,
  "page": 1,
  "size": 20,
  "categories": ["前端", "算法", "系统设计"]
}
```

**实现**：`Database.list_questions(filters) -> (items, total)` + `Database.list_categories()` 拼装。

#### 2.1.2 单条删除
```http
DELETE /api/questions/{id}
```
**顺序**（安全失败方向）：
1. `VectorStore.delete_by_id(id)` ← 先做，失败立即返回 500
2. `Database.delete_by_id(id)` ← 再做，失败返回 500（此时 ChromaDB 已删，列表会少一条但聊天搜不到——符合"安全失败"原则，最坏情况是双写都还在）

**Response 200**：`{"deleted": true, "id": "..."}`
**Response 404**：`{"detail": "题目不存在", "status_code": 404}`
**Response 500**：`{"detail": "删除失败: <原因>", "status_code": 500}`

#### 2.1.3 撤销：单条插入
```http
POST /api/ingest/insert-one
```
**Request**（`InsertOneRequest`）：
```json
{
  "question": "...",
  "answer": "...",
  "category": "...",
  "difficulty": "中等",
  "source": "user_undo_<timestamp>"
}
```
**后端 id 生成**：`md5(f"{question}|{answer}").hexdigest()[:16]`

**Response 201**：`Question` 对象
**Response 409**：`{"detail": "题目已存在", "status_code": 409}`（content_hash 冲突）

#### 2.1.4 异步导入（改造现有）
```http
POST /api/ingest/upload       (multipart)
POST /api/ingest              (JSON: md/pdf/url)
```
**新行为**：立即返回 202 + task_id（不再等 30-60s）
**Response 202**：`{"task_id": "uuid"}`

```http
GET /api/ingest/tasks/{task_id}
```
**Response**（`TaskStatusResponse`）：
```json
{
  "task_id": "uuid",
  "status": "pending|running|done|failed",
  "source_type": "md",
  "source": "data/questions.md",
  "total": 200,
  "done": 87,
  "ingested": 80,
  "duplicates": 5,
  "errors": 2,
  "started_at": "...",
  "finished_at": null,
  "error_message": null
}
```

```http
GET /api/ingest/tasks
```
**Response**：`{"tasks": [TaskStatusResponse, ...]}`（仅 status in pending|running）

### 2.2 异步任务状态机

```
[POST] ── pending ──▶ running ──▶ done
                       │  │
                       │  └────▶ failed (任一步抛异常)
                       │
                       └── (主进程重启) ──▶ task 丢失（用户需重新提交）
```

**`TaskStore` 实现**（`backend/app/services/task_store.py`）：
- 模块级单例 `tasks: dict[str, Task] = {}`
- `Task` 是 `@dataclass`，字段同 `TaskStatusResponse`
- 后台协程用 `asyncio.create_task` 跑在 FastAPI 事件循环里
- 任务完成/失败后**不立即删除**，保留 1 小时后清理（让前端能查询最终结果）

**前端轮询**：`useIngestTask` 用 `setInterval(1000ms)`，status=done|failed 时停止轮询并展示结果。

### 2.3 撤销数据流

```
[用户点删除]
    ↓
[DeleteConfirmDialog] 显示题面+答案预览
    ↓ 用户点确认
[DELETE /api/questions/{id}]    ← 后端：先 ChromaDB 再 SQLite
    ↓ 200 OK
[前端缓存 id + question + answer + category + difficulty + source 到 Map]
    ↓
[UndoToast 出现，5 秒倒计时]
    ↓ 用户点「撤销」
[POST /api/ingest/insert-one]   ← 携带缓存的完整字段
    ↓ 201 OK
[Toast「已恢复」+ 列表重新拉取]
```

**撤销冲突**：后端返回 409 → 前端 Toast「撤销失败，该题已存在」。

## 3. 关键技术决策

### 3.1 删除一致性：先 ChromaDB 后 SQLite

**原因**：
- ChromaDB 删失败 → 整批回滚（两边都还在）— 列表+聊天一致
- ChromaDB 删成功，SQLite 删失败 → 列表少一条但聊天搜不到 — **唯一可能的"不一致"**——但这是「聊天→列表」方向的不一致（用户感受不强），不是「列表→聊天」（诡异）
- 反之（先 SQLite 再 ChromaDB）：列表少一条但聊天能搜到，**用户会反复刷新以为系统 bug**——这是最糟的失败方向

### 3.2 路径白名单 + 遍历防护

**`backend/app/core/path_guard.py`**：
```python
SAFE_DATA_DIR = Path("./data").resolve()

def validate_safe_path(rel_path: str) -> Path:
    """仅允许 data/ 下的相对路径"""
    # 1. 拒绝绝对路径
    if Path(rel_path).is_absolute():
        raise PathGuardError("绝对路径被拒绝")
    # 2. 拒绝包含 ..
    if ".." in rel_path.split("/"):
        raise PathGuardError("包含 .. 的路径被拒绝")
    # 3. resolve 后必须在 SAFE_DATA_DIR 内
    target = (SAFE_DATA_DIR / rel_path).resolve()
    if not str(target).startswith(str(SAFE_DATA_DIR)):
        raise PathGuardError("路径逃逸")
    # 4. 拒绝符号链接
    if target.is_symlink():
        raise PathGuardError("符号链接被拒绝")
    return target
```

**集成位置**：`IngestService.ingest_md` / `ingest_pdf` 入口处都加 `validate_safe_path` 调用；API 层的 `ingest_endpoint` 也加（双层保险）。

**Out of Scope**：`SAFE_DATA_DIR` 暂不通过环境变量配置，硬编码 `./data` 即可。

### 3.3 异步任务并发控制

**单实例假设**：FastAPI 进程单实例运行，内存 `dict` 安全。
**多进程/多实例**：不实现（VPS 单机部署够用，未来需要时换 Redis/Celery）。
**任务并发数**：同进程内**串行执行**任务（一次一个导入），避免智谱 Embedding API 限流。
**进度更新**：每解析完一批（50 题）就更新 `Task.done += 50`，前端轮询看到增量。

### 3.4 前端状态管理

#### 3.4.1 `useKnowledgeBase` Hook

```typescript
interface UseKnowledgeBase {
  items: Question[]
  total: number
  page: number
  size: number
  categories: string[]
  isLoading: boolean
  error: string | null
  filters: { q: string; category: string; difficulty: string }
  setFilter(key, value): void   // 触发 debounce + 重新拉取
  setPage(page): void
  refresh(): void
}
```

**Debounce 策略**：搜索框输入 300ms debounce 后拉取；分页/分类/难度切换立即拉取。

#### 3.4.2 `useIngestTask` Hook

```typescript
interface UseIngestTask {
  task: TaskStatus | null
  isPolling: boolean
  start(taskId: string): void
  stop(): void
}
```

**轮询实现**：`setInterval(1000)`，status=done|failed 时 `clearInterval`。
**模态框关闭后**：`useIngestTask` 仍持有 taskId，Toast 出现「导入中...」并显示进度。
**服务端重启**（任务丢失）：轮询返回 404 → Toast「导入任务已丢失」+「重新导入」按钮。

### 3.5 Sidebar 路由切换

**当前状态**：`Sidebar.tsx:25` 有 `const [activeTab, setActiveTab] = useState<Tab>('conversations')`
**改造**：
```typescript
import { usePathname, useRouter } from 'next/navigation'
const pathname = usePathname()
const router = useRouter()
const activeTab = pathname === '/kb' ? 'knowledge' : 'conversations'

const handleTabClick = (tab: Tab) => {
  router.push(tab === 'conversations' ? '/' : '/kb')
}
```

**`/kb` 路由**：`frontend/app/kb/page.tsx` 直接复用同一个 `<Sidebar>` + 替换 `<ChatHistory>`/`<ChatInput>` 为知识库内容。

## 4. 兼容性

### 4.1 现有 API 兼容性

| 现有 | 兼容性 | 说明 |
|---|---|---|
| `POST /api/ingest/upload` | ⚠️ 行为变更 | 从同步返回 `IngestResponse` 改为异步返回 `task_id`。如果前端或脚本依赖原行为，需同步改造。**目前 `api.ts:91-104` 只有 `ingest` 调 JSON 路径，`upload` 没被前端调用。** |
| `POST /api/ingest` | ⚠️ 行为变更 | 同上 |
| `GET /api/stats` | ✅ 不变 | 仍可独立用 |
| `GET /api/health` | ✅ 不变 | |

**回滚方案**：如果异步改造出问题，把 `task_store.py` 的 `asyncio.create_task` 改回直接 `await` 即可，前后端契约无破坏性差异（前端代码还没合到主分支）。

### 4.2 数据兼容性

- 现有 SQLite `questions` 表结构不变，仅新增查询/删除方法
- ChromaDB collection 不变，仅新增 `delete_by_id` 方法
- 不修改任何已有数据

### 4.3 前端路由兼容

- 新增 `/kb` 路由不影响 `/`
- 用户直接访问 `/` 行为不变

## 5. 关键文件修改清单

| 文件 | 变更类型 | 风险 |
|---|---|---|
| `backend/app/api/ingest.py` | 改造 | 中（异步 + 新端点） |
| `backend/app/services/ingest_service.py` | 微调 | 中（拆 pipeline） |
| `backend/app/services/task_store.py` | 新增 | 低（纯内存） |
| `backend/app/core/path_guard.py` | 新增 | 低（独立模块） |
| `backend/app/core/vectorstore.py` | 新增 1 方法 | 低 |
| `backend/app/models/database.py` | 新增 3 方法 | 低 |
| `backend/app/models/schemas.py` | 新增 3 schema | 低 |
| `backend/app/api/questions.py` | 新增 | 低 |
| `backend/app/main.py` | 注册新 router | 低 |
| `backend/tests/test_questions.py` | 新增 | 低 |
| `backend/tests/test_task_store.py` | 新增 | 低 |
| `frontend/app/kb/page.tsx` | 新增 | 低 |
| `frontend/components/kb/*` | 新增 6 文件 | 低 |
| `frontend/components/layout/Sidebar.tsx` | 改造 | 中（路由切换） |
| `frontend/hooks/useKnowledgeBase.ts` | 新增 | 低 |
| `frontend/hooks/useIngestTask.ts` | 新增 | 低 |
| `frontend/lib/api.ts` | 扩展 | 低 |
| `frontend/lib/types.ts` | 扩展 | 低 |

## 6. 风险点与回滚

### 6.1 高风险点

| 风险 | 缓解 |
|---|---|
| 删除双写失败时数据不一致 | 顺序：先 ChromaDB 后 SQLite（安全失败） |
| 路径遍历漏洞 | `path_guard.py` 强校验，白名单 + 拒绝 .. |
| 异步任务在多进程下丢失 | 单实例假设（VPS），未来换 Redis |
| 撤销时 content_hash 冲突 | 后端 409 + 前端 Toast 提示 |
| `/api/ingest` 行为变更破坏外部调用 | 提前看 git log 确认无人外部调用（已确认前端只用 JSON ingest，且没合入上传到生产） |

### 6.2 回滚策略

**后端**：所有改造都是**新增**（新端点、新方法）+ ingest 异步化。如果新端点出问题，删除 router 注册 + 删除新文件即可，主分支行为不变。

**前端**：
- 新组件放在 `frontend/components/kb/` — 整体删除不影响 `/`
- `Sidebar.tsx` 改造：git revert 即可回滚
- 新路由 `frontend/app/kb/page.tsx` — 整体删除

### 6.3 数据回滚

- 删除操作不可逆（除非用户 5 秒内撤销）— 前端必须强调二次确认
- 不提供「批量回滚」或「软删除」恢复通道（YAGNI）
