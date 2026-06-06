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
