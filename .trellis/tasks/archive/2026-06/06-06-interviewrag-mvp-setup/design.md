# 技术设计：InterviewRAG

## 系统架构

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│  Next.js UI │────▶│  FastAPI Backend                          │
│  (Chat UI)  │ SSE │                                          │
└─────────────┘     │  ┌─────────┐  ┌──────────┐  ┌─────────┐ │
                    │  │ API层    │─▶│ RAG引擎   │─▶│ 智谱API  │ │
                    │  │(query/   │  │(LangChain)│  │(LLM+Emb)│ │
                    │  │ ingest)  │  └──────────┘  └─────────┘ │
                    │  └─────────┘       │                      │
                    │                    ▼                      │
                    │  ┌─────────────────────────────────┐     │
                    │  │ 混合检索层                        │     │
                    │  │ ┌──────────┐  ┌──────────────┐  │     │
                    │  │ │ ChromaDB │  │ BM25 索引     │  │     │
                    │  │ │(向量检索) │  │(关键词检索)   │  │     │
                    │  │ └──────────┘  └──────────────┘  │     │
                    │  └────────────┬────────────────────┘     │
                    │               ▼                          │
                    │  ┌─────────────────────┐                 │
                    │  │ Re-ranker            │                 │
                    │  │ (BGE-Reranker)       │                 │
                    │  └─────────────────────┘                 │
                    └──────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              ┌──────────┐      ┌──────────────┐    ┌──────────┐
              │ SQLite   │      │ ChromaDB     │    │ 评估模块  │
              │ (元数据)  │      │ (向量存储)    │    │ (RAGAS)  │
              └──────────┘      └──────────────┘    └──────────┘
```

## 模块设计

### 1. 数据采集层

**MD 解析器** (`parsers/md_parser.py`)
- 输入：MD 文件路径
- 解析逻辑：正则匹配 `###` 章节、`####` 题目、`参考答案` 内容
- 输出：`List[Question]` 统一格式

**网页爬虫** (`parsers/web_scraper.py`)
- 目标：掘金、CSDN 面试专栏
- 策略：requests + BeautifulSoup，提取文章标题和内容
- 频率限制：1 req/s，避免被封
- 输出：`List[Question]`

**PDF 解析器** (`parsers/pdf_parser.py`)
- 库：PyPDF2 或 Unstructured
- 逻辑：提取文本 → 按标题分块 → 识别题目和答案
- 输出：`List[Question]`

**统一数据格式**：
```python
class Question(BaseModel):
    id: str                    # 唯一标识
    question: str              # 题目文本
    answer: str                # 参考答案
    category: str              # 分类（LLM/VLM/RLHF/Agent/RAG/评估）
    difficulty: str            # 难度（简单/中等/困难）
    source: str                # 来源（文件名/URL）
    tags: list[str]            # 标签
    created_at: datetime       # 创建时间
```

### 2. RAG Pipeline（LangChain）

**文档分块**：
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", " "]
)
```

**混合检索器** (`retrievers/hybrid_retriever.py`)：
```python
class HybridRetriever:
    """自定义 LangChain Retriever，融合向量检索和 BM25"""

    def __init__(self, vectorstore, bm25_index, alpha=0.7):
        self.vectorstore = vectorstore      # ChromaDB
        self.bm25_index = bm25_index        # BM25 索引
        self.alpha = alpha                   # 向量权重（0.7向量 + 0.3关键词）

    def get_relevant_documents(self, query: str, k: int = 10):
        # 1. 向量检索
        vector_results = self.vectorstore.similarity_search_with_score(query, k=k)
        # 2. BM25 检索
        bm25_results = self.bm25_search(query, k=k)
        # 3. 加权融合 (RRF - Reciprocal Rank Fusion)
        merged = self.reciprocal_rank_fusion(vector_results, bm25_results)
        return merged[:k]
```

**Re-ranking** (`rerankers/bge_reranker.py`)：
```python
from sentence_transformers import CrossEncoder

class BGEReranker:
    def __init__(self, model_name="BAAI/bge-reranker-base"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, documents: list, top_k: int = 5):
        pairs = [(query, doc.page_content) for doc in documents]
        scores = self.model.predict(pairs)
        # 按分数排序，返回 top_k
        ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, score in ranked[:top_k]]
```

**查询改写** (`chains/query_rewriter.py`)：
```python
# 用 LLM 将口语化问题改写为精确查询
REWRITE_PROMPT = """
你是一个搜索查询优化器。用户的问题可能比较口语化或模糊。
请将其改写为更适合检索的精确查询，保持原意但更具体。

用户问题：{question}
改写后的查询：
"""
```

**RAG Chain** (`chains/rag_chain.py`)：
```
用户问题 → 查询改写 → 混合检索(k=20) → Re-ranking(top 5) → LLM 生成答案
```

### 3. 对话管理

**对话记忆**：
```python
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(
    k=10,  # 保留最近 10 轮
    return_messages=True,
    memory_key="chat_history"
)
```

**SSE 流式输出**：
```python
from fastapi.responses import StreamingResponse

async def stream_answer(question: str):
    async for chunk in rag_chain.astream(question):
        yield f"data: {json.dumps({'content': chunk})}\n\n"
    yield "data: [DONE]\n\n"
```

### 4. API 设计

```
POST /api/query
  Body: { "question": "什么是Transformer?", "conversation_id": "xxx" }
  Response: StreamingResponse (SSE) 或 JSON

POST /api/ingest
  Body: multipart/form-data (文件) 或 { "source": "url" }
  Response: { "ingested": 75, "duplicates": 0 }

GET /api/health
  Response: { "status": "ok", "vector_count": 75 }

GET /api/stats
  Response: { "total_questions": 75, "categories": {...}, "last_updated": "..." }
```

### 5. 评估体系

**RAGAS 评估**：
```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

result = evaluate(
    dataset=eval_dataset,  # 20 道评估题
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
)
```

**对比实验**：
| 方案 | 检索策略 | Re-ranking |
|------|----------|------------|
| A（基线） | 纯向量检索 | 无 |
| B | 混合检索 | 无 |
| C | 混合检索 | BGE-Reranker |
| D | 小块检索+大块生成 | 无 |

---

## 目录结构

```
InterviewRAG/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── api/                 # API 路由
│   │   │   ├── query.py
│   │   │   ├── ingest.py
│   │   │   ├── health.py
│   │   │   └── stats.py
│   │   ├── chains/              # LangChain 链
│   │   │   ├── rag_chain.py     # 主 RAG 链
│   │   │   └── query_rewriter.py
│   │   ├── retrievers/          # 自定义检索器
│   │   │   └── hybrid_retriever.py
│   │   ├── rerankers/           # Re-ranking
│   │   │   └── bge_reranker.py
│   │   ├── parsers/             # 数据解析器
│   │   │   ├── md_parser.py
│   │   │   ├── web_scraper.py
│   │   │   └── pdf_parser.py
│   │   ├── models/              # 数据模型
│   │   │   ├── schemas.py
│   │   │   └── database.py
│   │   ├── services/            # 业务逻辑
│   │   │   ├── rag_service.py
│   │   │   ├── embed_service.py
│   │   │   └── llm_service.py
│   │   ├── core/                # 核心工具
│   │   │   ├── vectorstore.py
│   │   │   └── exceptions.py
│   │   └── utils/
│   │       └── text_splitter.py
│   ├── evaluation/              # 评估模块
│   │   ├── eval_dataset.json    # 评估数据集
│   │   ├── ragas_eval.py        # RAGAS 评估脚本
│   │   └── comparison.py        # 对比实验
│   ├── data/
│   │   ├── raw/                 # 原始数据
│   │   ├── processed/           # 解析后的 JSON
│   │   └── chroma/              # ChromaDB 存储
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   └── package.json
└── README.md
```
