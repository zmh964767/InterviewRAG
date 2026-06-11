# InterviewRAG

基于 RAG（检索增强生成）的面试题库问答系统。

## ✨ 特性

- **高级 RAG Pipeline**：LangChain 链式调用 + 混合检索（向量+BM25）+ Re-ranking
- **小块检索、大块生成**：Small-to-Big 策略，检索更精准，生成更完整
- **多数据源采集**：MD 解析 + 网页爬虫 + PDF 解析
- **多轮对话**：支持上下文记忆的连续追问
- **流式输出**：SSE 实时返回答案，首字延迟 < 1s
- **代码语法高亮**：highlight.js + github-dark 主题，Python/JS/JSON 等 190+ 种语言
- **RAGAS 评估**：Faithfulness、Relevancy、Precision、Recall 四项指标
- **评估报告 Web UI**：`/eval` 页面展示最新指标 + 历史快照（无需终端 `cat report.md`）
- **对比实验**：四种检索策略效果对比
- **代码质量**：ESLint 8 + Next.js TypeScript 规则，0 warnings

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
│   │   ├── api/          # API 路由（query/ingest/eval/questions/health/stats）
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
│   ├── app/              # Next.js 页面（/ /kb /eval）
│   ├── components/       # React 组件
│   │   ├── chat/         # 对话组件（ChatMessage / ChatHistory / ChatInput）
│   │   ├── eval/         # 评估组件（RagMetricsBar / ComparisonTable）
│   │   ├── kb/           # 知识库组件
│   │   ├── layout/       # Sidebar 等布局组件
│   │   └── sources/      # 来源引用组件
│   ├── contexts/         # React Context（ChatContext）
│   ├── hooks/            # 自定义 Hooks（useConversations adapter）
│   └── lib/              # API 封装 + 类型定义
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

### 3. 知识库管理

访问 `http://localhost:3000/kb`：
- 查看题目列表（支持搜索、分类、难度过滤）
- 上传 md/pdf 文件或输入 URL 导入
- 删除单条题目（5 秒内可撤销）

### 4. 评估系统

**Web UI**（推荐）：访问 `http://localhost:3000/eval`，查看最新指标 + 历史快照列表，点击展开详情。

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
npm test          # 20 个 ChatContext 单测（CRUD + 持久化 + 流式 partial 同步）
npm run lint      # ESLint 检查（0 warnings / errors）
```

## 📊 检索策略对比

| 方案 | 检索策略 | Re-ranking |
|------|----------|------------|
| A（基线） | 纯向量检索 | 无 |
| B | 混合检索（向量+BM25） | 无 |
| C | 混合检索 | BGE-Reranker |
| D | 小块检索+大块生成 | 无 |
| **E（新增）** | **多路 Query 改写 + 混合检索** | 无 |

方案 E 用 LLM 把单条 query 改写成 3 个语义等价变体，**多路并发检索后按 chunk id 去重合并**（score 取 max），覆盖同义表达与口语化查询。失败/超时自动回退到单路混合检索。`SKIP_RERANKER=1` 仍生效。

## 📝 API 文档

启动后端后访问：`http://localhost:8080/docs`

**主要端点**：
- `POST /api/query` — 问答（支持流式 SSE）
- `GET /api/questions` — 题目列表（分页+过滤）
- `POST /api/ingest/upload` — 上传文件导入
- `POST /api/ingest/insert-one` — 单条插入（撤销用）
- `DELETE /api/questions/{id}` — 删除单条
- `GET /api/eval/summary` — 评估汇总（最新 + 历史快照列表）
- `GET /api/eval/detail?ts=<ISO>` — 评估详情（latest 或指定历史快照）
- `GET /api/health` — 健康检查
- `GET /api/stats` — 知识库统计

## 🔧 调优记录

### 检索链路调优（2026-06-11）

通过**单变量 sweep**（5 Prompt 变体 + 4 Chunk size）调优 strategy E（多路改写 + 混合检索）的 HR@5。

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

## License

MIT
