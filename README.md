# InterviewRAG

基于 RAG（检索增强生成）的面试题库问答系统。

## ✨ 特性

- **高级 RAG Pipeline**：LangChain 链式调用 + 混合检索（向量+BM25）+ Re-ranking
- **小块检索、大块生成**：Small-to-Big 策略，检索更精准，生成更完整
- **多数据源采集**：MD 解析 + 网页爬虫 + PDF 解析
- **多轮对话**：支持上下文记忆的连续追问
- **流式输出**：SSE 实时返回答案，首字延迟 < 1s
- **RAGAS 评估**：Faithfulness、Relevancy、Precision、Recall 四项指标
- **对比实验**：四种检索策略效果对比

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
| 评估 | RAGAS |

## 📁 项目结构

```
InterviewRAG/
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── chains/       # LangChain 链
│   │   ├── retrievers/   # 检索器（混合、小块大块）
│   │   ├── rerankers/    # Re-ranking
│   │   ├── parsers/      # 数据解析（MD/PDF/网页）
│   │   ├── models/       # 数据模型
│   │   ├── services/     # 业务逻辑
│   │   └── core/         # 核心工具
│   ├── evaluation/       # 评估模块
│   └── data/             # 数据存储
├── frontend/
│   ├── app/              # Next.js 页面
│   ├── components/       # React 组件
│   ├── lib/              # API 封装
│   └── hooks/            # 自定义 Hooks
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

## 📊 检索策略对比

| 方案 | 检索策略 | Re-ranking |
|------|----------|------------|
| A（基线） | 纯向量检索 | 无 |
| B | 混合检索（向量+BM25） | 无 |
| C | 混合检索 | BGE-Reranker |
| D | 小块检索+大块生成 | 无 |

## 📝 API 文档

启动后端后访问：`http://localhost:8080/docs`

**主要端点**：
- `POST /api/query` — 问答（支持流式 SSE）
- `GET /api/questions` — 题目列表（分页+过滤）
- `POST /api/ingest/upload` — 上传文件导入
- `POST /api/ingest/insert-one` — 单条插入（撤销用）
- `DELETE /api/questions/{id}` — 删除单条
- `GET /api/health` — 健康检查
- `GET /api/stats` — 知识库统计

## License

MIT
