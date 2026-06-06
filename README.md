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

# 导入数据
python -m app.parsers.md_parser data/raw/Extra01-参考答案.md data/processed/questions.json
python -m app.cli ingest --source data/processed/questions.json

# 启动服务
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
```

### 3. 评估

```bash
cd backend
python -m evaluation.ragas_eval
python -m evaluation.comparison
```

## 📊 检索策略对比

| 方案 | 检索策略 | Re-ranking |
|------|----------|------------|
| A（基线） | 纯向量检索 | 无 |
| B | 混合检索（向量+BM25） | 无 |
| C | 混合检索 | BGE-Reranker |
| D | 小块检索+大块生成 | 无 |

## 📝 API 文档

启动后端后访问：`http://localhost:8000/docs`

## License

MIT
