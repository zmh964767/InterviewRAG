# 知识库管理 UI

## Goal

为已存在的 ChromaDB + SQLite 知识库添加可视化界面，让用户能查看、添加、删除面试题，不必再通过 curl 调 API 或操作服务器文件。

## Confirmed Facts（来自代码）

### 后端已有能力
- `POST /api/ingest`（[backend/app/api/ingest.py:25-40]）— 通过 **服务端文件路径**或 URL 导入：`{source, source_type: 'md'|'pdf'|'url'}`
- `POST /api/ingest/upload`（[backend/app/api/ingest.py:43-58]）— Multipart 文件上传（仅支持 `.md` / `.pdf`）
- `GET /api/stats`（[backend/app/api/stats.py:26-42]）— 返回 `{total_questions, categories, last_updated}`（从 SQLite 读）
- `GET /api/health`（[backend/app/api/health.py:43-67]）— 健康检查 + vector_count
- `IngestService` 支持 `ingest_json`（[backend/app/services/ingest_service.py:54-63]）— 但 API 未暴露
- `Database` 有 `insert_question` / `get_all_questions` / `get_question_by_id` / `count`（[backend/app/models/database.py]）
- `VectorStore` 有 `add_documents` / `query` / `count` / `delete_all` / `get_all`（[backend/app/core/vectorstore.py]）
- SQLite 表 `questions` 字段：`id, question, answer, category, difficulty, source, tags, content_hash, created_at`

### 后端缺失能力
- ❌ 删除单条题目（SQLite 有 content_hash 去重，但 ChromaDB 没 delete-by-id 方法）
- ❌ 更新题目（需删除旧向量 + 重新 Embedding）
- ❌ 列表分页/搜索/按分类过滤
- ❌ 单条题目查看 API（`get_question_by_id` 已存在但没暴露成 API）
- ❌ JSON 导入未在 API 暴露

### 前端已有结构
- 单页 SPA，只有 `/` 一个路由（[frontend/app/page.tsx]）
- Sidebar 已有 **「对话」/「知识库」** 两个 Tab（[frontend/components/layout/Sidebar.tsx:18,79-94]）
- 「知识库」Tab 当前只展示只读统计：题目数 + 分类列表（[frontend/components/layout/Sidebar.tsx:147-194]）
- `getStats()` 已在 page.tsx 调用，注入 Sidebar

### 前端类型已有
- `StatsResponse`、`IngestRequest`、`IngestResponse`、`QueryRequest`（[frontend/lib/types.ts]）
- 缺失：完整的 `Question` 类型、QuestionList 响应、Question 查询参数

### 业务约束（来自 Schema）
- 题目是"题+答"配对的，删除必须 **SQLite + ChromaDB 同步**
- 重复判定基于 `md5(question|answer)`（[backend/app/models/database.py:48-49]）
- 智谱 Embedding API 单次最多 64 条（[backend/app/services/ingest_service.py:99]），分批 50

## Scope (用户已选 A 方案)

### In Scope（MVP 范围）
- ✅ 列表查看（分页、按分类/关键词过滤）
- ✅ 删除单条题目（SQLite + ChromaDB 同步）
- ✅ 上传 md / pdf 文件
- ✅ URL 导入
- ✅ 撤销机制（删除后 5 秒内可撤销）

### Out of Scope（MVP 暂不做）
- ❌ 编辑单条题目（避免 ChromaDB 重建 + 旧引用失效问题）
- ❌ 标签管理（现有 tags 字段但 UI 不暴露）
- ❌ 评估/质量评分
- ❌ 权限管理（无登录态）
- ❌ 知识库多租户/多 collection
- ❌ 批量删除/批量操作
- ❌ JSON 导入（只支持 md/pdf/url，JSON 给程序化脚本用）
- ❌ 服务端文件路径导入的「白名单目录」可配置化（先用 `data/` 硬编码）

## Confirmed Decisions

- **Scope 范围**：A 方案（只读+导入+删除+列表查询，不含编辑）
- **UI 形态**：C 方案 — 全屏独立页 `/kb`，顶部导航加「对话 / 知识库」切换器
- **列表形态**：C 方案 — 紧凑表格 + 右侧详情抽屉（点开行后看完整题面+答案）
- **导入入口**：A+C 组合 — 顶部工具栏「+ 导入」按钮 + 模态框（3 Tab：上传文件 / URL / 服务端路径）
- **JSON 导入**：不做（只支持 md/pdf/url，JSON 给程序化脚本用）
- **删除策略**：D 方案 — 二次确认弹窗（含题面+答案预览） + 删除后 5 秒 Toast「撤销」
- **撤销机制**：前端在删除前缓存题面+答案，撤销时 POST `/api/ingest/insert-one` 重新插入
- **列表查询能力**：C 方案 — 服务端分页 + 关键词（题面+答案） + 分类过滤 + 难度过滤
- **默认分页 size**：20（适配桌面端屏幕；超过 20 时支持滚动加载或翻页器）
- **删除一致性**：A 方案 — 后端 `DELETE /api/questions/{id}` 内部**先删 ChromaDB → 再删 SQLite**（"安全失败"方向：最坏情况是双写都还在，不会出现"列表看不到但聊天能搜"的诡异状态）
- **insert-one id 生成**：A 方案 — 后端基于 `md5(question|answer)[:16]` 生成稳定 id（保证撤销时复用同一 id）
- **撤销冲突处理**：a 方案 — 静默失败 + Toast 提示「撤销失败，该题已存在」（5 秒内重复上传造成 content_hash 冲突时）
- **导入进度**：B 方案 — 任务队列 + 轮询（POST 202 → GET `/api/ingest/tasks/{task_id}` 1s 轮询，进度/错误/重复数实时显示）
- **路由切换**：C 方案 — 复用 Sidebar，顶部「对话 / 知识库」Tab 升级为路由切换（`router.push('/' | '/kb')`），两个页面共用 Sidebar 视觉，主区域换为各自内容
- **列表列定义**：B 方案（5 列）
  - ID（80px，等宽字体显示前 8 字符）
  - 题面（flex，前 60 字符+省略号）
  - 分类（120px，可排序）
  - 难度（80px，可排序）
  - 创建时间（140px，可排序，默认 desc）
  - 右侧固定操作列（查看详情 / 删除）
- **导入 Tab 顺序**：A 方案 — 1) 上传文件  2) URL  3) 服务端路径
- **服务端路径安全加固**（必做）：
  - 仅允许 `data/` 白名单目录下的相对路径
  - 拒绝包含 `..` 的路径
  - 拒绝绝对路径
  - 拒绝符号链接
  - 解决现有 `IngestService.ingest_md` 直接 `open(任意路径)` 的路径遍历漏洞
- **详情抽屉内容**：C 方案 — 业务 5 字段 + 元数据
  - ID（短哈希全显示）
  - 分类 / 难度
  - 来源 / 创建时间
  - 题目（完整）
  - 参考答案（完整）
  - 标签（如有则显示，无则显示 [无]）
  - 顶部「返回 / 删除 / 关闭」按钮
  - 抽屉宽度：480-600px
- **移动端**：B 方案 — 简化卡片视图（<1024px 用卡片列表代替表格，抽屉变全屏；<768px 操作按钮移至底部固定栏）

## Acceptance Criteria

### 后端 API
- [ ] `GET /api/questions?page=1&size=20&q=&category=&difficulty=` 返回 `{items, total, page, size, categories}`，支持 4 过滤维度；size 默认 20，最大 100
- [ ] `POST /api/ingest/insert-one` 用 `md5(question|answer)[:16]` 作为稳定 id；重复内容返回 409
- [ ] `DELETE /api/questions/{id}` 先删 ChromaDB 再删 SQLite；任一步失败不继续
- [ ] `POST /api/ingest/upload`、`POST /api/ingest`（md/pdf/url）改为异步：返回 202 + task_id
- [ ] `GET /api/ingest/tasks/{task_id}` 返回 `{status: pending|running|done|failed, total, done, ingested, duplicates, errors}`
- [ ] `GET /api/ingest/tasks` 列出所有未完成任务
- [ ] 服务端路径导入做白名单 + 路径遍历校验（拒绝 `..`、绝对路径、符号链接）
- [ ] `VectorStore.delete_by_id(id)` 新增
- [ ] `Database.delete_by_id(id)`、`Database.list_questions(filters)`、`Database.list_categories()` 新增
- [ ] 上述 4 个新方法 + 3 个新 API 都有 pytest 测试覆盖

### 前端 `/kb` 页面
- [ ] `frontend/app/kb/page.tsx` 存在，路由可访问
- [ ] Sidebar 顶部「对话 / 知识库」点击切换路由（`router.push`）
- [ ] `/kb` 页面工具栏：「+ 导入」按钮 + 搜索框 + 分类下拉 + 难度下拉
- [ ] 表格列：ID(80px) / 题面(flex) / 分类(120px) / 难度(80px) / 创建时间(140px) + 操作列
- [ ] 创建时间默认 desc，可点击列头切换排序
- [ ] 点击行打开右侧详情抽屉（480-600px），显示 5 业务字段 + 3 元数据字段
- [ ] 删除按钮 → 二次确认弹窗（含题面+答案预览）→ 删除后 5 秒 Toast「撤销」
- [ ] 撤销调用 `POST /api/ingest/insert-one`，失败时 Toast「撤销失败」不报错
- [ ] 导入模态框 3 Tab：上传文件 / URL / 服务端路径（顺序按使用频率）
- [ ] 导入后 1s 轮询 task 状态，进度条 + 完成结果（新增/重复/失败）
- [ ] 模态框关闭后任务在后台跑，Toast「导入中...」可点查看
- [ ] <1024px 切卡片视图，<768px 操作按钮移至底部固定栏

## Notes

- 复杂度：**Complex**（涉及前后端、删除一致性、撤销机制、安全加固、异步任务）— 需要 `design.md` + `implement.md`
- 拆分子任务建议：parent = 当前任务，children = ①后端 API ②前端页面 ③测试 — 但每个子任务不强依赖，可独立归档
- 风险点：删除一致性是单点故障，路径遍历是安全 issue，需要 `trellis-check` 重点扫
