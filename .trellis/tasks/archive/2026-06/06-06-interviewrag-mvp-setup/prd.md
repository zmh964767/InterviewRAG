# PRD: InterviewRAG — 基于 RAG 的面试题库问答系统

## 目标

构建一个**生产级**的 RAG 面试题库问答系统，展示完整的 RAG 工程能力。支持多数据源采集、高级检索策略、多轮对话、流式输出、自动化评估。

## 用户价值

- 求职者获得精准、有上下文的面试准备
- 答案来源于真实题库（非幻觉），并附带来源引用
- 支持多轮追问，模拟真实面试场景
- 语义搜索 + 关键词搜索混合，召回更准

## 简历亮点

- 完整 RAG Pipeline：文档解析 → 分块 → 向量化 → 混合检索 → Re-ranking → 生成
- 多数据源采集：MD 解析 + 网页爬虫 + PDF 解析
- LangChain 链式编排 + 自定义 Retriever
- RAGAS 自动化评估体系
- 多轮对话 + 流式输出（SSE）

---

## 技术栈

| 层 | 技术 |
|---|---|
| LLM | 智谱 GLM-4-Flash |
| Embedding | 智谱 embedding-3 |
| 向量数据库 | ChromaDB |
| 关键词检索 | BM25（rank_bm25） |
| RAG 编排 | LangChain |
| Re-ranking | BGE-Reranker (sentence-transformers) |
| 后端 | FastAPI (Python) |
| 前端 | Next.js (React + Tailwind) |
| 元数据 | SQLite |
| 评估 | RAGAS |

---

## 需求

### R1: 多数据源采集与解析
- **MD 解析器**：解析已有 MD 面试题文件（`###` 章节 → `####` 题目 → 答案）
- **网页爬虫**：从掘金/CSDN/知乎抓取面试文章，提取结构化题目
- **PDF 解析**：支持 PDF 格式的面试题导入
- **统一格式**：所有来源转为 `{id, question, answer, category, difficulty, source, tags}` JSON
- **增量导入**：支持追加新题目，不重复

### R2: 高级 RAG Pipeline
- **文档分块**：RecursiveCharacterTextSplitter，chunk_size=500，overlap=50
- **混合检索**：向量相似度 + BM25 关键词搜索，加权融合
- **Re-ranking**：用 BGE-Reranker 对检索结果重排序
- **查询改写**：用 LLM 将用户口语化问题改写为更精确的检索查询
- **LangChain 链式调用**：自定义 Retriever + LLMChain 编排

### R3: 多轮对话与流式输出
- **对话记忆**：ConversationBufferMemory，保持上下文连贯
- **SSE 流式输出**：答案逐字返回，前端实时展示
- **来源引用**：每个回答附带原始题目 ID 和相关度分数
- **兜底处理**：上下文不足时返回"我暂时无法回答这个问题"

### R4: 前端界面
- 对话式 Chat UI（类似 ChatGPT）
- 消息列表 + 输入框 + 发送按钮
- 答案中高亮显示来源引用
- 加载状态、错误提示
- 移动端响应式

### R5: API 层
- `POST /api/query` — 问答（支持流式）
- `POST /api/ingest` — 知识库导入
- `GET /api/health` — 健康检查
- `GET /api/stats` — 知识库统计
- 错误处理 + 请求校验 + CORS

### R6: 评估体系
- **RAGAS 指标**：Faithfulness、Answer Relevancy、Context Precision、Context Recall
- **测试数据集**：准备 20 道评估问题 + 标准答案
- **自动化评估脚本**：一键运行评估，输出指标报告
- **对比实验**：基础检索 vs 混合检索 vs 混合+Re-ranking 效果对比

---

## 验收标准

- [ ] 75 道面试题全部导入并可搜索
- [ ] 混合检索 + Re-ranking 比纯向量检索召回率提升 20%+
- [ ] 用户能多轮追问，系统保持上下文连贯
- [ ] 答案通过 SSE 流式返回，首字延迟 < 1s
- [ ] 每个回答附带来源引用（题目 ID + 分数）
- [ ] RAGAS 评估四项指标均 > 0.7
- [ ] 前端 Chat UI 正常工作，移动端可用
- [ ] API 返回正确错误码（400、404、500）
- [ ] 核心流程有单元测试 + 集成测试

---

## 已确定决策

1. ✅ **LLM**：智谱 GLM-4-Flash
2. ✅ **Embedding**：智谱 embedding-3
3. ✅ **向量数据库**：ChromaDB
4. ✅ **RAG 编排**：LangChain
5. ✅ **Re-ranking**：BGE-Reranker
6. ✅ **后端**：FastAPI
7. ✅ **前端**：Next.js
8. ✅ **元数据**：SQLite
9. ✅ **数据来源**：MD 解析 + 网页爬虫 + PDF 解析
10. ✅ **评估**：RAGAS

---

## 阶段划分

### Phase 1：数据层（Day 1-2）
- MD 解析脚本
- 网页爬虫
- PDF 解析
- 统一 JSON 格式 + 导入 ChromaDB

### Phase 2：RAG 核心（Day 2-3）
- LangChain + 智谱 API 集成
- 混合检索（向量 + BM25）
- Re-ranking
- 查询改写

### Phase 3：对话与 API（Day 3-4）
- 多轮对话记忆
- SSE 流式输出
- FastAPI 端点
- 错误处理

### Phase 4：前端（Day 4-5）
- Next.js Chat UI
- SSE 接入
- 来源引用展示

### Phase 5：评估（Day 5-6）
- RAGAS 评估脚本
- 测试数据集
- 对比实验

### Phase 6：打磨（Day 6-7）
- 测试补全
- 文档完善
- 性能优化
