# 后端质量规范

> InterviewRAG 后端代码质量标准

---

## 必须遵守的模式

- 所有 API 端点必须有 Pydantic 请求/响应模型
- 所有外部调用（智谱 API、ChromaDB）必须有超时和重试
- 所有函数必须有类型标注
- 所有模块必须有 docstring

---

## 禁止模式

- ❌ 不用 `print()` 输出日志，用 `logging` 模块
- ❌ 不在代码里硬编码 API Key 或密钥
- ❌ 不用 `from module import *`
- ❌ 不写超过 50 行的函数（拆分）
- ❌ 不用可变默认参数（`def f(x=[])` 错误，用 `def f(x=None)`）

---

## 测试要求

- 核心服务（`rag_service`、`embed_service`）必须有单元测试
- API 端点必须有集成测试
- 测试覆盖率目标：核心流程 80%+
- 测试用 pytest，不用 unittest

---

## 代码审查清单

- [ ] 函数有类型标注
- [ ] 异常用自定义异常类
- [ ] 外部调用有超时处理
- [ ] 没有硬编码的密钥
- [ ] 日志级别正确（info/warning/error）
- [ ] 测试覆盖核心逻辑

---

## 踩坑记录（实战经验）

### 1. 智谱 Embedding API 批量限制
**问题**：智谱 embedding API 单次最多 64 条，超过会报错 `input单次不得超过64条`。
**解决**：导入时分批处理，每批 50 条。
**位置**：`services/ingest_service.py` 的 `_ingest_questions()` 方法。

### 2. ChromaDB 自定义 Embedding 函数
**问题**：ChromaDB 默认使用 ONNX 模型做 embedding，下载慢且不支持中文。
**解决**：实现 `ZhipuEmbeddingFunction` 类，继承 `chromadb.api.types.EmbeddingFunction`，调用智谱 API。
**注意**：已有 collection 不能更换 embedding function，需要先删除旧 collection。

### 3. FastAPI 服务单例模式
**问题**：每次请求都 `new RAGService()` 会重复创建 VectorStore、LLMService 等重量级对象。
**解决**：用模块级 `_get_rag_service()` 单例，首次调用时创建，后续复用。

### 4. 智谱 SDK 异步流式调用
**问题**：`zhipuai` SDK 的 `stream=True` 返回同步迭代器，直接在 async 函数中使用会阻塞事件循环。
**解决**：用 `asyncio.get_event_loop().run_in_executor()` 包装，在线程池中执行。

### 5. Next.js 配置文件格式
**问题**：旧版 Next.js 不支持 `next.config.ts`，需要 `.mjs` 或 `.js`。
**解决**：重命名为 `next.config.mjs`，移除 TypeScript 类型注解。

### 6. Windows 端口占用
**问题**：Windows 上 `taskkill` 后端口可能不立即释放。
**解决**：用 `taskkill //F //IM python.exe` 强制杀进程，或换端口号。

### 7. RAGAS 0.4.3 + 智谱 LLM 集成
**问题**：RAGAS 0.4.3 的 collections metrics（Faithfulness/AnswerRelevancy 等）不接受 langchain `LangchainLLMWrapper`，必须用 `InstructorLLM`。
**解决**：用 `openai.AsyncOpenAI` + `ragas.llms.llm_factory` 创建 `InstructorLLM`。
```python
from openai import AsyncOpenAI
from ragas.llms import llm_factory
client = AsyncOpenAI(api_key=key, base_url="https://open.bigmodel.cn/api/paas/v4/")
llm = llm_factory("glm-4-flash", client=client)
```
**注意**：`llm_factory` 的 `**kwargs` 会透传给 `InstructorLLM.__init__`，不能同时传 `model_args`（会冲突）。max_tokens 通过 `InstructorModelArgs` 设置。

### 8. RAGAS faithfulness 输出截断
**问题**：智谱 glm-4-flash 单次输出上限 ~4096 tokens，faithfulness 评估需要 ~6000+ tokens（15 个 statements + verdicts + reasons），导致 `finish_reason='length'` 截断。
**解决**：目前无法绕过（模型本身限制）。faithfulness 分数偶尔偏低是正常的，不影响其他 3 个指标（answer_relevancy/context_precision/context_recall 通常够用）。
**规避**：用更短的答案做评估，或换更高 max_tokens 的模型（glm-4-long）。

### 9. BGE Re-ranker Windows 加载卡死
**问题**：`sentence_transformers.CrossEncoder('BAAI/bge-reranker-base')` 在 Windows 上加载 1.1G 模型时 hang 死（>8 分钟无响应）。
**解决**：通过 `SKIP_RERANKER=1` 环境变量跳过加载。
```python
# bge_reranker.py
if os.environ.get("SKIP_RERANKER", "").lower() in ("1", "true", "yes"):
    return  # 跳过加载
```
**位置**：`app/rerankers/bge_reranker.py` 的 `_ensure_loaded()` 方法。

### 10. 评估数据集必须用改写题目
**问题**：用 ChromaDB 里的原题做评估，所有检索策略命中率相同（HR@5=0.8929），没有区分度。
**解决**：用不同措辞的改写题目（paraphrase），测试真正的语义检索能力。改写题目的 Hit Rate 应该用**关键词重叠 + 子串匹配**（不是 SequenceMatcher 文本相似度）。
**结论**：混合检索（向量+BM25）在改写题目上比纯向量高 50%。
