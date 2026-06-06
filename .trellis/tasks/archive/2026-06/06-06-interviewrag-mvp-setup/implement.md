# 实现计划：InterviewRAG

## 执行顺序

按 Phase 分批实现，每批完成后验证再继续。

---

## Phase 1：项目骨架 + 数据层（Day 1-2）

### 1.1 后端项目初始化
- [ ] 创建 `backend/` 目录结构
- [ ] `requirements.txt`：fastapi, uvicorn, langchain, langchain-community, chromadb, zhipuai, rank_bm25, sentence-transformers, ragas, pypdf2, beautifulsoup4, pydantic, python-dotenv
- [ ] `.env.example`：ZHIPU_API_KEY, CHROMA_PERSIST_DIR, SQLITE_DB_PATH
- [ ] `app/config.py`：pydantic-settings 环境变量管理
- [ ] `app/main.py`：FastAPI 基础应用 + CORS + 异常处理器

### 1.2 MD 解析器
- [ ] `parsers/md_parser.py`：正则解析 `###` 章节、`####` 题目、`参考答案`
- [ ] 输出 `List[Question]` 统一格式
- [ ] 处理 HTML 标签（`<strong>` 等）清理
- [ ] 测试：解析 75 道题，验证完整性

### 1.3 网页爬虫
- [ ] `parsers/web_scraper.py`：requests + BeautifulSoup
- [ ] 支持掘金面试专栏文章抓取
- [ ] 频率限制 + User-Agent 伪装
- [ ] 输出 `List[Question]`

### 1.4 PDF 解析器
- [ ] `parsers/pdf_parser.py`：PyPDF2 提取文本
- [ ] 按标题模式识别题目和答案
- [ ] 输出 `List[Question]`

### 1.5 数据导入
- [ ] `services/ingest_service.py`：JSON → 分块 → 向量化 → ChromaDB
- [ ] SQLite 元数据存储
- [ ] 去重逻辑（基于 question 文本 hash）
- [ ] CLI 脚本：`python -m app.cli ingest --source data/raw/`

### 验证
```bash
# 解析 MD 文件
python -m app.parsers.md_parser data/raw/Extra01-参考答案.md -o data/processed/questions.json

# 导入到 ChromaDB
python -m app.cli ingest --source data/processed/questions.json

# 验证导入
python -m app.cli stats
# 预期：75 questions, 6 categories
```

---

## Phase 2：RAG 核心（Day 2-3）

### 2.1 智谱 API 集成
- [ ] `services/llm_service.py`：封装 zhipuai SDK
- [ ] 支持普通调用 + 流式调用
- [ ] 错误处理 + 重试逻辑
- [ ] `services/embed_service.py`：embedding-3 封装

### 2.2 LangChain 集成
- [ ] `chains/rag_chain.py`：LangChain LLMChain 编排
- [ ] 自定义 `ZhipuLLM` wrapper（如果 langchain 不直接支持智谱）
- [ ] Prompt 模板：系统提示 + 上下文 + 问题

### 2.3 混合检索器
- [ ] `retrievers/hybrid_retriever.py`：
  - 向量检索（ChromaDB）
  - BM25 关键词检索（rank_bm25）
  - RRF 融合算法
- [ ] 自定义 LangChain BaseRetriever 接口

### 2.4 Re-ranking
- [ ] `rerankers/bge_reranker.py`：BGE-Reranker 加载 + 推理
- [ ] 集成到 RAG Chain 的检索后处理

### 2.5 查询改写
- [ ] `chains/query_rewriter.py`：LLM 查询改写
- [ ] 集成到 RAG Chain 的检索前处理

### 验证
```bash
# 单元测试
pytest tests/test_hybrid_retriever.py -v
pytest tests/test_reranker.py -v

# 手动测试 RAG Chain
python -m app.cli query "什么是Transformer的自注意力机制？"
# 预期：返回有依据的答案 + 来源引用
```

---

## Phase 3：对话 + API（Day 3-4）

### 3.1 多轮对话
- [ ] ConversationBufferWindowMemory（保留 10 轮）
- [ ] 对话 ID 管理（UUID）
- [ ] 上下文注入到 RAG Chain

### 3.2 SSE 流式输出
- [ ] FastAPI StreamingResponse
- [ ] 前端 EventSource 接入
- [ ] 错误处理：流中断时发送错误事件

### 3.3 API 端点
- [ ] `POST /api/query` — 问答（支持流式）
- [ ] `POST /api/ingest` — 知识库导入
- [ ] `GET /api/health` — 健康检查
- [ ] `GET /api/stats` — 知识库统计
- [ ] 请求校验（Pydantic Schema）
- [ ] CORS 配置

### 3.4 错误处理
- [ ] 自定义异常类（AppError 子类）
- [ ] 全局异常处理器
- [ ] 日志记录

### 验证
```bash
# 启动后端
uvicorn app.main:app --reload

# 测试 API
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是Transformer?"}'

# 测试流式
curl -N -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是Transformer?", "stream": true}'

# 健康检查
curl http://localhost:8000/api/health
```

---

## Phase 4：前端（Day 4-5）

### 4.1 Next.js 项目初始化
- [ ] `npx create-next-app@latest frontend --typescript --tailwind`
- [ ] 目录结构：app/, components/, lib/, hooks/

### 4.2 Chat UI 组件
- [ ] `components/chat/ChatInput.tsx`：输入框 + 发送按钮
- [ ] `components/chat/ChatMessage.tsx`：消息气泡（区分用户/AI）
- [ ] `components/chat/ChatHistory.tsx`：消息列表 + 自动滚动
- [ ] `components/sources/SourceCard.tsx`：来源引用卡片
- [ ] `components/ui/Loading.tsx`：加载动画
- [ ] `components/ui/ErrorDisplay.tsx`：错误提示

### 4.3 SSE 接入
- [ ] `lib/api.ts`：fetch + EventSource 封装
- [ ] `hooks/useChat.ts`：对话状态管理 + SSE 流式接收
- [ ] 逐字显示效果

### 4.4 页面
- [ ] `app/page.tsx`：Chat 主页面
- [ ] `app/layout.tsx`：全局布局

### 验证
```bash
cd frontend
npm run dev
# 浏览器打开 http://localhost:3000
# 输入问题，验证流式回答 + 来源引用
```

---

## Phase 5：评估（Day 5-6）

### 5.1 评估数据集
- [ ] `evaluation/eval_dataset.json`：20 道评估题
  - 5 道来自已有题库（测试召回）
  - 5 道改述题（测试语义理解）
  - 5 道跨分类题（测试泛化）
  - 5 道无关题（测试兜底）

### 5.2 RAGAS 评估脚本
- [ ] `evaluation/ragas_eval.py`：
  - 加载评估数据集
  - 运行 RAG Chain 获取预测
  - 计算四项指标
  - 输出报告

### 5.3 对比实验
- [ ] `evaluation/comparison.py`：
  - 方案 A：纯向量检索
  - 方案 B：混合检索
  - 方案 C：混合检索 + Re-ranking
  - 输出对比表格

### 验证
```bash
# 运行评估
python -m evaluation.ragas_eval

# 运行对比实验
python -m evaluation.comparison

# 预期输出：
# | 方案 | Faithfulness | Relevancy | Precision | Recall |
# |------|-------------|-----------|-----------|--------|
# | A    | 0.72        | 0.68      | 0.65      | 0.70   |
# | B    | 0.78        | 0.74      | 0.72      | 0.76   |
# | C    | 0.82        | 0.79      | 0.78      | 0.81   |
```

---

## Phase 6：测试 + 文档（Day 6-7）

### 6.1 测试
- [ ] `tests/test_parsers.py`：解析器单元测试
- [ ] `tests/test_retriever.py`：检索器单元测试
- [ ] `tests/test_api.py`：API 集成测试
- [ ] `tests/test_rag_chain.py`：RAG Chain 端到端测试

### 6.2 文档
- [ ] `README.md`：项目介绍、快速开始、架构图
- [ ] API 文档：FastAPI 自动生成（/docs）
- [ ] 部署说明

### 6.3 性能优化
- [ ] Embedding 缓存（避免重复计算）
- [ ] Re-ranker 模型预加载
- [ ] ChromaDB 索引优化

---

## 风险与回退

| 风险 | 影响 | 回退方案 |
|------|------|----------|
| 智谱 API 限流 | 生成变慢 | 加重试 + 降级到非流式 |
| BGE-Reranker 下载慢 | 环境搭建耗时 | 先跳过 Re-ranking，用纯混合检索 |
| LangChain 版本兼容 | 接口变动 | 锁定版本，必要时降级 |
| 网页爬虫被封 | 数据源受限 | 先只用 MD 文件，爬虫作为加分项 |
