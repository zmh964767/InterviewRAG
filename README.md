# InterviewRAG

基于 RAG（检索增强生成）的面试题库问答系统。

## ✨ 特性

- **高级 RAG Pipeline**：LangChain 链式调用 + 混合检索（向量+BM25）+ Re-ranking
- **小块检索、大块生成**：Small-to-Big 策略，检索更精准，生成更完整
- **多数据源采集**：MD 解析 + 网页爬虫 + PDF 解析
- **多轮对话**：支持上下文记忆的连续追问
- **流式输出**：SSE 实时返回答案，首字延迟 < 1s
- **流式控制**：停止/重新生成，切对话时流后台继续
- **暗色模式**：全站 light/dark 切换，跟随系统偏好，localStorage 持久化，inline script 防闪烁
- **代码语法高亮**：highlight.js + github-dark 主题，Python/JS/JSON 等 190+ 种语言
- **RAGAS 评估**：Faithfulness、Relevancy、Precision、Recall 四项指标
- **评估报告 Web UI**：`/admin/eval` 5 个 tab：概览 / 题目详情 / 历史快照 / 对比 / Sweep
- **用户反馈系统**：公开端 👍/👎 按钮 + 可选 comment；管理端「反馈」tab 展示统计/列表/导出 CSV/跳回原对话
- **对比实验**：四种检索策略效果对比
- **骨架屏加载**：列表/报告加载时显示 shimmer 占位
- **无障碍**：focus-visible ring + Modal 焦点陷阱 + skip link + prefers-reduced-motion
- **双端架构**：用户端（匿名访问问答 + 题目库只读）+ 管理端（JWT 鉴权的知识库/评估后台）

## 🏗️ 技术栈

| 层 | 技术 |
|---|---|
| LLM | 智谱 GLM-4-Flash |
| Embedding | 智谱 embedding-3 |
| 向量数据库 | ChromaDB |
| 关键词检索 | BM25 (rank_bm25) |
| RAG 编排 | LangChain |
| Re-ranking | BGE-Reranker |
| 后端 | FastAPI (Python) |
| 前端 | Next.js (React + Tailwind) |
| 代码高亮 | highlight.js + rehype-highlight |
| 评估 | RAGAS |
| 测试 | Vitest + React Testing Library |
| 代码质量 | ESLint 8 (next/core-web-vitals + next/typescript) |

## 📁 项目结构

```
InterviewRAG/
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由（query/questions/health/auth/admin/*）
│   │   ├── chains/       # LangChain 链
│   │   ├── retrievers/   # 检索器（混合、小块大块）
│   │   ├── rerankers/    # Re-ranking
│   │   ├── parsers/      # 数据解析（MD/PDF/网页）
│   │   ├── models/       # 数据模型
│   │   ├── services/     # 业务逻辑
│   │   └── core/         # 核心工具
│   ├── evaluation/       # 评估模块（结果在 results/ 下）
│   └── data/             # 数据存储
├── frontend/
│   ├── app/              # Next.js 页面（/ /questions /admin/*）
│   ├── components/       # React 组件
│   │   ├── a11y/         # 无障碍组件（Modal 焦点陷阱）
│   │   ├── chat/         # 对话组件（ChatMessage / ChatHistory / ChatInput / InlineErrorBanner）
│   │   ├── eval/         # 评估组件（RagMetricsBar / ComparisonTable）
│   │   ├── kb/           # 知识库组件
│   │   ├── layout/       # Sidebar 等布局组件
│   │   ├── sources/      # 来源引用组件
│   │   └── ui/           # 通用 UI（Skeleton / ErrorBanner）
│   ├── contexts/         # React Context（ChatContext）
│   ├── hooks/            # 自定义 Hooks（useConversations adapter）
│   └── lib/              # API 封装 + 类型定义 + 文案常量（copy.ts）
└── README.md
```

## 🚀 快速开始

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 ZHIPU_API_KEY

# 启动服务（默认端口 8080）
SKIP_RERANKER=1 uvicorn app.main:app --reload --port 8080
```

> **注意**：`SKIP_RERANKER=1` 跳过 BGE Re-ranker 加载（Windows 上加载卡死）。如需 Re-ranker，去掉此环境变量。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
```

### 3. 题目库（用户端只读）

访问 `http://localhost:3000/questions`：
- 查看题目列表（支持搜索、分类、难度过滤）
- 匿名访问，无需登录

### 4. 管理后台

访问 `http://localhost:3000/admin/login`，输入 `ADMIN_PASSWORD`（默认 `admin123`）登录：
- 仪表盘（统计总览 + 最近评估指标 + 加载骨架屏）
- 知识库管理（`/admin/kb`）：上传 md/pdf/URL 导入、删除单条（5 秒内可撤销）
- 评估报告（`/admin/eval`）：最新指标 + 历史快照列表 + 骨架屏加载

JWT 存于 `localStorage.admin_token`，过期/失效自动跳转登录页。

**命令行**（运行新评估）：

```bash
cd backend

# 快速评估（~2 分钟，只跑检索对比）
SKIP_RERANKER=1 python -m evaluation.run --mode comparison --skip-regression

# 完整评估（~30 分钟，含 RAGAS 4 指标）
SKIP_RERANKER=1 python -m evaluation.run --mode ragas --skip-regression

# 查看报告
cat evaluation/report.md
```

**评估模式**：
- `comparison`：4 种检索策略对比（Hit Rate@5 + MRR）
- `ragas`：RAGAS 4 指标（faithfulness/answer_relevancy/context_precision/context_recall）
- `sanity`：快速链路验证（不调 RAGAS）
- `full`：ragas + comparison

**环境变量**：
- `SKIP_RERANKER=1`：跳过 BGE Re-ranker（Windows 必需）
- `ZHIPU_API_KEY`：智谱 API 密钥（.env 文件配置）

### 5. 测试

```bash
cd frontend
npm test          # 23 个 ChatContext 单测（CRUD + 持久化 + 流式 partial 同步 + abort + 重新生成）
npm run lint      # ESLint 检查（0 warnings / errors）
npx tsc --noEmit  # TypeScript 类型检查（0 errors）
```

## 📊 检索策略对比

| 方案 | 检索策略 | Re-ranking |
|------|----------|------------|
| A（基线） | 纯向量检索 | 无 |
| B | 混合检索（向量+BM25） | 无 |
| C | 混合检索 | BGE-Reranker |
| D | 小块检索+大块生成 | 无 |
| **E** | **多路 Query 改写 + 混合检索** | 无 |

方案 E 用 LLM 把单条 query 改写成 3 个语义等价变体，多路并发检索后按 chunk id 去重合并（score 取 max），覆盖同义表达与口语化查询。失败/超时自动回退到单路混合检索。

## 🎨 UI/UX 打磨（2026-06-12）

通过 5 个 commit 完成前端体验打磨：

| 块 | 内容 | 改动量 |
|---|---|---|
| A | 流式停止按钮 + 错误条 + 重新生成 | 8 文件 |
| B | Dashboard 加载/错误态 + Skeleton + ErrorBanner | 5 文件 |
| C | 可访问性：Modal 焦点陷阱 + skip link + focus-visible + prefers-reduced-motion | 13 文件 |
| D | Race condition 修复 + 切会话不清流还原 | 6 文件 |
| E | 骨架屏 + 字符串抽常量（copy.ts） | 5 文件 |

**关键改进**：
- 流式可中断：Stop 按钮 + AbortController UI 接入 + 切对话时流后台继续
- 可访问性：20+ aria-label、focus-visible ring、Modal 焦点陷阱（inert + Tab 回退）、skip link、prefers-reduced-motion
- 加载体验：骨架屏替代"加载中..."文字，shimmer 动画
- 错误处理：ErrorBanner 替代 window.alert，InlineErrorBanner 替代 `[错误: ...]` 拼接
- 文案集中：`frontend/lib/copy.ts` 7 组常量（CHAT/STATE/ADMIN/A11Y/QUESTIONS/EVAL/KB）

## 📝 API 文档

启动后端后访问：`http://localhost:8080/docs`

**主要端点**：
- `POST /api/auth/login` — 管理员登录（密码 → JWT）
- `POST /api/query` — 问答（支持流式 SSE，公开）
- `GET /api/questions` — 题目列表（公开，分页+过滤）
- `GET /api/health` — 健康检查（公开）
- `GET /api/admin/stats` — 知识库统计（需 JWT）
- `POST /api/admin/ingest/upload` — 上传文件导入（需 JWT）
- `POST /api/admin/ingest/insert-one` — 单条插入（撤销用，需 JWT）
- `DELETE /api/admin/questions/{id}` — 删除单条（需 JWT）
- `GET /api/admin/eval/summary` — 评估汇总（需 JWT）
- `GET /api/admin/eval/detail?ts=<ISO>` — 评估详情（需 JWT）

## 🔧 调优记录

### 检索链路调优（2026-06-11）

通过单变量 sweep（5 Prompt 变体 + 4 Chunk size）调优 strategy E（多路改写 + 混合检索）的 HR@5。

**运行 sweep**：
```bash
cd backend
python -m evaluation.sweep
```

**Prompt 变体**（5 个，见 `backend/app/retrievers/prompts/query_rewrite_v*.txt`）：
- v1: 基线（现状）
- v2: 面试特化（保留技术术语）
- v3: few-shot（示例引导）
- v4: 高温度 0.7（鼓励多样性）
- v5: 极简约束（自由泛化）

**Chunk size**（4 个）：200 / 500 / 800 / 1200，overlap 固定 10%

**结果存放**：`backend/evaluation/results/sweep/`（本地，不提交 git）

## 🚧 下一步

### 高优先级

| 方向 | 说明 | 预估工作量 |
|---|---|---|
| **Docker 部署** | Dockerfile + docker-compose（前端 + 后端 + ChromaDB），一键启动 | 1 天 |
| ~~**流式性能优化**~~ | ~~`mergePartialIntoConversation` 每 token 全数组重建 → 改用 `useReducer`；react-markdown 逐 token 重解析 → 50ms 节流~~ ✅ | ~~1-2 天~~ |
| **后端单测补全** | `services/` + `api/` 单测覆盖率补齐（当前只有前端 23 个单测） | 1 天 |
| ~~**知识库批量操作**~~ | ~~多选 + 批量删除 + 批量导入~~ ✅ | ~~1 天~~ |

### 中优先级

| 方向 | 说明 | 预估工作量 |
|---|---|---|
| ~~**暗色模式**~~ | ~~CSS 变量双套映射 + 主题切换 + 用户偏好持久化~~ ✅ | ~~2 天~~ |
| **完整 i18n** | 引入 next-intl，copy.ts 已铺路（7 组常量），只换 dictionary loader | 1 天 |
| **管理端移动端适配** | admin 侧边栏 256px 固定宽度 → 响应式折叠 | 半天 |
| ~~**评估历史对比**~~ | ~~两次评估快照的指标 diff 展示~~ ✅ | ~~1 天~~ |
| ~~**Sweep 参数扫描 UI**~~ | ~~`evaluation/sweep.py` 结果展示 + winner 推荐~~ ✅ | ~~1 天~~ |
| ~~**用户反馈系统**~~ | ~~对回答点赞/点踩 + 反馈收集 + 管理端统计/列表/导出 CSV + 跳回原对话~~ ✅ | ~~1 天~~ |

### 低优先级

| 方向 | 说明 | 预估工作量 |
|---|---|---|
| **知识库版本管理** | 导入/删除操作的版本快照 + 回滚 | 2 天 |
| **反馈数据 → Sweep 关联** | 把差评率低的 prompt variant 自动标记,辅助 sweep 调优 | 1 天 |
| **多模型支持** | 接入 OpenAI / Claude 等其他 LLM | 1 天 |
| **Redis 会话存储** | 后端 conversations 从内存 dict 迁移到 Redis | 半天 |

## License

MIT
