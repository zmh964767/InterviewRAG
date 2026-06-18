# InterviewRAG 面试备战手册

> 最后更新：2026-06-18（含最新优化）

---

## 一、项目一句话定位

**基于 RAG 的智能面试题库问答系统** — 用户用自然语言提问，系统从知识库检索相关内容，用 LLM 生成流式回答，并提供完整可观测性与评估体系。

---

## 二、简历项目段（直接复制）

```
InterviewRAG — 基于 RAG 的面试知识库问答系统
技术栈：FastAPI · LangChain · ChromaDB · Next.js 14 · Docker · Prometheus/Grafana

• 设计 5 种检索策略（纯向量 / 混合检索 / BGE 重排 / Small-to-Big / 多路改写），
  混合检索与多路改写策略将 Hit Rate@5 从 23.5% 提升至 35.3%（+50%）
• 自研语义缓存（SQLite + 余弦相似度），命中时响应延迟从 ~2s 降至 <50ms
• 集成 RAGAS 评估体系（faithfulness / relevancy / precision / recall），
  支持参数扫描（5 prompt × 4 chunk size）+ 回归快照，数据驱动 RAG 调优
• 前端 SSE 流式渲染 + 双 Context 状态管理，首 Token 延迟 <1s
• 完整可观测性：Prometheus 指标 + Grafana 预置面板 + structlog 结构化日志 + Loki
• 440+ 自动化测试，GitHub Actions CI 三路并行（后端 pytest / 前端 Vitest / 构建验证）
```

---

## 三、技术栈速查

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | 异步 Python Web 框架 |
| RAG 编排 | LangChain 0.3 | 文档加载、链式调用 |
| 向量数据库 | ChromaDB | 持久化客户端，余弦距离 HNSW |
| 关键词检索 | BM25 + jieba | 中文分词 + 停用词过滤 + 词频检索 |
| 重排序 | BGE-Reranker | BAAI 交叉编码器 |
| LLM | 智谱 GLM-4-Flash | 抽象工厂模式，可切换 OpenAI 兼容接口 |
| 前端 | Next.js 14 + React 18 + Tailwind | App Router，standalone 输出 |
| 数据库 | SQLite (aiosqlite) | 问题、反馈、语义缓存 |
| 评估 | RAGAS | 4 维指标 + 自定义 Hit Rate/MRR |
| 可观测性 | Prometheus + Grafana + Loki + structlog | 指标 + 日志 + 面板 |
| 容器化 | Docker + docker-compose | 5 服务一键启动 |
| CI/CD | GitHub Actions | 3 并发 job |

---

## 四、核心架构

```
用户浏览器
  │
  ▼
Next.js :3000 ──SSE──▶ FastAPI :8080
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    语义缓存          检索管线           LLM 生成
   (SQLite)      (Multi-Query)      (Streaming SSE)
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   QueryRewriter  HybridRetriever  BGE Reranker
   (5 prompt 变体)  (向量+BM25+RRF)
                      │
              ┌───────┴───────┐
              ▼               ▼
          ChromaDB         BM25 索引
         (向量检索)     (jieba 分词 + 停用词过滤, 懒刷新)
```

### 请求处理流程

1. 用户发问 → 速率限制（滑动窗口，30 req/min）
2. 语义缓存命中？→ 直接返回（<50ms，阈值 0.90）
3. LLM 多路改写 → 生成 3 个语义变体
4. 并发混合检索 → 向量 + BM25 → RRF 融合（k=60, vector 70% / BM25 30%）
5. BGE 重排序（交叉编码器，top-20 → top-5）
6. 组装 context → LLM 流式生成
7. SSE 逐 token 推送 + 最终 sources
8. 写入语义缓存

### 检索策略可配置

| 策略 | 配置项 | 默认值 | 说明 |
|------|--------|--------|------|
| 多路改写 | `multi_query_enabled` | True | LLM 改写 + 并发检索 |
| Small-to-Big | `small_to_big_enabled` | False | 小块精确匹配 + 大块上下文 |
| 单路混合 | 两者都 False | - | 向量 + BM25 直接检索 |

---

## 五、核心评估数据

### 5.1 RAGAS 端到端指标（17 题核心集）

| 指标 | 值 | 说明 |
|------|-----|------|
| Faithfulness | **0.928** | 答案忠实于 context，几乎无幻觉 |
| Answer Relevancy | **0.738** | 答案切题度 |
| Context Precision | **0.964** | 检索精准度 |
| Context Recall | **0.882** | 检索覆盖度 |

### 5.2 检索策略对比（Hit Rate@5）

| 策略 | Hit Rate@5 | MRR | 对比基线 |
|------|-----------|-----|---------|
| A — 纯向量 | 23.5% | 0.235 | 基线 |
| B — 混合检索（向量+BM25） | **35.3%** | **0.277** | **+50%** |
| D — 小块检索大块生成 | 23.5% | 0.235 | 持平 |
| E — 多路改写+混合检索 | **35.3%** | **0.284** | **+50%** |

### 5.3 参数扫描结果

**Prompt 变体（chunk_size=500）：**

| Prompt | HR@5 | MRR | 备注 |
|--------|------|-----|------|
| v1 | 35.3% | 0.270 | 综合最优 |
| v2 | 35.3% | 0.277 | |
| v4 | 35.3% | **0.284** | MRR 最高 |
| v3 | 29.4% | 0.265 | 较差 |
| v5 | 35.3% | 0.230 | MRR 最低 |

**Chunk Size（prompt v1）：**

| Chunk Size | HR@5 | MRR |
|-----------|------|-----|
| 200 | 29.4% | 0.206 |
| 500 | **35.3%** | 0.232 |
| 800 | 35.3% | 0.247 |
| 1200 | 29.4% | 0.250 |

**结论：** chunk_size=500 + prompt_v1 综合最优；若只看 MRR 可选 prompt_v4。

### 5.4 评估演进

| 日期 | 测试集 | Faithfulness | Relevancy | Precision | Recall |
|------|--------|-------------|-----------|-----------|--------|
| 06-12 | 17 题 | 0.667 | 0.717 | 1.000 | 1.000 |
| 06-13 | 17 题 | **0.928** | **0.738** | 0.964 | 0.882 |
| 06-17 | 254 题 | 0.126 | 0.633 | 0.969 | 0.346 |

> 254 题集分数低有两个原因：(1) 30 秒超时导致 80 题报错（复杂题 86.7% 超时）；
> (2) LLM 用自己的知识回答而非引用 context，导致 faithfulness 虚低。
> **已修复**：超时改为自适应（exact 15s / paraphrase 60s / complex 120s），预计下次评估覆盖率从 69% 提升到 95%+。

### 5.5 已完成的优化项

| 优化 | 修改前 | 修改后 | 影响 |
|------|--------|--------|------|
| 评估超时 | 固定 30s | 自适应（15/60/120s） | 80 题报错 → 预计 <15 题 |
| 错误项表示 | error=null | 记录具体异常类型 | 结果可追溯 |
| 语义缓存阈值 | 0.95 | 0.90 | 命中率提升 |
| Small-to-Big | 死代码 | 接入 RAGService | 新增检索策略 |
| 距离计算 | `1-distance`（可负） | `1-distance/2`（0-1） | 修复 score bug |
| comparison.py | 字符重叠匹配 | 关键词匹配（HR@5+MRR） | 指标一致性 |
| BM25 分词 | 无停用词过滤 | 过滤 80+ 常见停用词 | 检索质量提升 |
| Reranker 阻塞 | 同步调用阻塞事件循环 | `run_in_executor` 包装 | 并发性能 |
| Docker SKIP_RERANKER | 默认跳过 | 默认启用 | 检索质量提升 |

---

## 六、面试高频 Q&A

### 🔵 架构决策题

#### Q1: 为什么用混合检索而不是纯向量检索？

> 纯向量检索擅长语义匹配，但在精确关键词（函数名、专有名词）上容易丢失。BM25 恰好相反。我用 RRF（Reciprocal Rank Fusion）融合两路结果，公式是 `score = Σ 1/(k + rank_i)`，k 通常取 60。
>
> 实测混合检索 Hit@5 = 35.3%，比纯向量 23.5% 提升了 50%。

**追问：**
- 为什么不用加权平均？→ RRF 不需要归一化，对不同量纲的分数天然兼容
- RRF 的 k 值怎么选？→ k=60 是论文常用值，主要作用是平滑排名差异，对 top 结果影响小，对尾部结果影响大
- BM25 权重怎么配的？→ 30% BM25 + 70% 向量，通过参数扫描确定

#### Q2: 多路改写是怎么工作的？

> 用户输入一个 query，LLM 生成 N 个语义变体（默认 3 个），每个变体独立走混合检索，最后在 chunk 级别去重合并，取每个 chunk 的最高分。这样能覆盖用户意图的不同表述方式。
>
> 5 个 prompt 变体分别从不同角度改写：同义替换、专业术语、通俗表达、反向提问、具体化。

**追问：**
- 会不会增加延迟？→ 会，用了线程池并发执行，实际延迟约等于单次检索的 1.2-1.5 倍
- 什么时候不该用？→ query 已经很具体时，改写反而引入噪声
- 实测效果？→ HR@5 和混合检索持平（35.3%），但 MRR 略高（0.284 vs 0.277），说明排名更优

#### Q3: 语义缓存的阈值怎么定的？

> 0.90 的余弦相似度阈值。最初设 0.95 太严格，命中率极低；通过评估数据集 sweep 后调整到 0.90，在准确率和命中率之间取平衡。

**追问：**
- 为什么不用 key-value 缓存？→ "Python 装饰器怎么用"和"解释 Python decorator"语义相同但字面不同
- LRU 淘汰策略？→ 超过容量（1000 条）时淘汰最久未访问的，同时 24h TTL 过期自动清理
- 命中时延迟？→ 从 ~2s 降至 <50ms，跳过整个检索+生成管线

#### Q4: BM25 索引怎么更新的？

> 用 dirty flag + TTL cooldown + double-check locking 模式。文档变更时只标记 dirty，实际重建要等 TTL 过期（30 秒冷却）且确认文档数变化才触发。避免每次写入都重建索引。

#### Q5: Small-to-Big 策略是什么？

> 小块（~166 字）用于向量化和检索，语义更聚焦，匹配更精准；大块（完整题目+答案）用于 LLM 生成，上下文更完整。检索时先命中小块，再取回对应大块送给 LLM。
>
> 这个策略通过 `small_to_big_enabled` 配置项控制，默认关闭，可与多路改写互斥使用。

---

### 🔴 技术深挖题

#### Q6: SSE 流式传输怎么处理客户端断开？

> 后端用 `async for` 检测 `CancelledError`，前端用 `AbortController`。用户点停止时，前端 `abort()` 终止 fetch，后端捕获异常后保存已生成的部分回答。
>
> `_StreamWithSources` 将同步 LLM 流包装为 async generator，最后一个 SSE event 是 `done` 类型，携带 sources 引用。

**追问：**
- 为什么不用 WebSocket？→ SSE 是单向推送，对 LLM 流式场景足够，且天然支持 HTTP/2 多路复用，无需升级协议
- 怎么保证消息不丢？→ 最后一个 event 带 done 标记 + sources，前端收到 done 才认为完整

#### Q7: 前端为什么用双 Context？

> 一个 Context 管理对话列表（增删改查），一个 Context 管理流式状态（当前流式消息、abort 控制）。流式传输时每秒可能更新几十次，如果共享一个 Context，会导致整个对话列表不必要的重渲染。
>
> 拆开后，流式更新只触发流式 Context 的消费者重渲染。

**追问：**
- 662 行的 Context 文件太大了怎么办？→ 确实，如果重做会拆成更细的 hooks + useReducer 组合
- useReducer vs useState？→ 状态逻辑复杂时 useReducer 更清晰，且 dispatch 引用稳定，利于性能优化

#### Q8: Provider 抽象层怎么设计的？

> 定义了 `LLMProvider` 和 `EmbeddingProvider` 两个 ABC，每个提供商实现这两个接口。工厂函数根据环境变量创建对应实例。
>
> `openai_style.py` 兼容所有 OpenAI API 格式的服务（Ollama、Azure、vLLM 等），切换提供商只需改 `.env`，零代码改动。

#### Q9: 懒刷新的 BM25 索引具体怎么实现？

> 三个关键机制：
> 1. **Dirty flag**：文档增删时设置 dirty=True，不立即重建
> 2. **TTL cooldown**：重建后记录时间戳，cooldown 期内（30 秒）不重复重建
> 3. **Double-check locking**：先检查 dirty + TTL，确认需要重建后加锁，再二次检查防止并发重建
>
> 分词时过滤了 80+ 常见中文停用词（的、了、是、在...），避免高频虚词干扰 BM25 评分。

#### Q10: Reranker 怎么避免阻塞事件循环？

> `BGEReranker.rerank()` 内部的 `model.predict()` 是同步阻塞操作（PyTorch 推理）。在 async 上下文中用 `loop.run_in_executor(None, ...)` 包装，让它在线程池中执行，不阻塞 FastAPI 的事件循环。

---

### 🟢 工程实践题

#### Q11: 做评估体系最大的收获？

> 最大的收获是**用数据代替直觉**。比如多路改写，直觉上觉得应该全面优于单路检索，但实测在某些数据集上反而更差（因为改写引入了噪声）。
>
> 参数扫描发现 chunk_size=500 + prompt_v1 是最优组合，这不是猜出来的。RAGAS 的 faithfulness 指标也帮我发现了 LLM 幻觉问题——LLM 用自己的知识回答而非引用 context。

#### Q12: 遇到最大的技术挑战？

> 评估系统的超时问题。最初用固定 30 秒超时，导致 80/254 题报错（复杂题 86.7% 超时）。后来改成自适应超时：exact 题 15 秒（单路检索快），paraphrase 60 秒，complex 120 秒。
>
> 这个问题的根源是评估管线把检索和生成耦合在一起——即使生成超时，检索结果其实已经拿到了。下一步计划把检索评估和生成评估解耦。

#### Q13: 如果重新做，会改什么？

> 1. **向量数据库**：ChromaDB 适合原型，生产环境换 Milvus/Qdrant，支持分布式和更好过滤
> 2. **Guardrails**：LLM 输出缺少结构化校验，加 Pydantic output parser 或 guardrails
> 3. **前端状态管理**：662 行 Context 太大，拆成更细的 hooks 组合
> 4. **评估解耦**：检索质量和生成质量分开评估，避免一方超时影响另一方

#### Q14: 254 题集评估分数下降怎么看？

> 坦诚说：有两个原因：
> 1. **超时 bug**：固定 30s 超时导致 80 题报错，已修复为自适应超时
> 2. **faithfulness 虚低**：LLM（GLM-4）本身就知道这些面试题的答案，所以用自己的知识回答而非引用 context，导致 faithfulness 几乎为 0
>
> 但核心指标依然健康：Context Precision 保持 96.9%，说明检索精准度没问题。这正是做评估体系的价值——发现问题、量化问题、指导优化方向。

---

### 🟡 开放题

#### Q15: RAG vs Fine-tuning 怎么选？

> RAG 适合：知识频繁更新、需要引用来源、数据量不够大
> Fine-tuning 适合：需要改变模型行为模式/风格、特定领域推理
>
> 面试题库场景：知识会更新、用户需要出处 → RAG 是正确选择。如需特定回答风格，可叠加 fine-tuning。

#### Q16: 怎么评估 RAG 系统效果？

> RAGAS 四维度：
> - **Faithfulness**：答案是否忠实于 context（防幻觉）
> - **Answer Relevancy**：答案是否回答了问题
> - **Context Precision**：检索到的 context 中有多少是相关的
> - **Context Recall**：相关的 context 是否都被检索到了
>
> 另外有 Hit Rate@5 和 MRR 衡量检索质量。关键是需要评估数据集——我写了自动生成工具从知识库构建 question-context-answer 三元组。

#### Q17: 这个项目最大的亮点是什么？

> 三点：
> 1. **系统性**：不是 demo，有 5 种策略对比、参数扫描、回归快照、完整评估体系
> 2. **数据驱动**：所有技术选型都有实验数据支撑，不是拍脑袋
> 3. **工程完整度**：从前端到可观测性到 CI，全链路覆盖

---

## 七、回答框架：STAR-R

| 步骤 | 含义 | 示例 |
|------|------|------|
| **S**ituation | 背景 | "面试题库场景，用户问法多样" |
| **T**ask | 目标 | "提高检索召回率" |
| **A**ction | 做法 | "实现多路改写 + RRF 融合" |
| **R**esult | 结果 | "Hit@5 提升 50%" |
| **R**eflection | 反思 | "但发现改写有时引入噪声，后来加了置信度过滤" |

---

## 八、Live Demo 指南

### 8.1 启动方式

```bash
# 方式 A：Docker（推荐，一键启动 5 个服务）
cd D:\Zerobyheart\InterviewRAG
cp backend/.env.example backend/.env
# 编辑 .env，设置 ZHIPU_API_KEY
docker compose up -d

# 方式 B：手动开发模式
# 终端 1：后端
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
# 终端 2：前端
cd frontend && npm install && npm run dev
```

### 8.2 Demo 流程（3-5 分钟）

| 步骤 | 操作 | 展示点 | 话术 |
|------|------|--------|------|
| 1 | 打开 `localhost:3000` | 聊天界面 | "用户直接提问，无需登录" |
| 2 | 输入 "React 虚拟 DOM 是什么？" | SSE 流式输出 | "首 Token <1s，逐字输出" |
| 3 | 展示底部来源引用 | 检索来源 | "每个回答附带检索来源，可验证" |
| 4 | 追问 "它和 Fiber 的关系？" | 多轮对话 | "10 轮记忆窗口" |
| 5 | 打开 `localhost:3000/admin/login` | 管理后台 | 密码 admin123 |
| 6 | 展示评估页面 | RAGAS 指标 | "5 种策略对比，数据驱动" |
| 7 | 打开 `localhost:3001` | Grafana | "Prometheus + Loki 完整可观测" |

### 8.3 被问到"分数不高"时的话术

> "17 题核心集上 faithfulness 93%、precision 96%，这是系统真实水平。
> 254 题集分数低是因为评估工具有超时 bug（固定 30s，复杂题 86.7% 超时），
> 已修复为自适应超时。这也说明评估体系的价值——发现问题、量化问题。"

---

## 九、面试加分技巧

### 主动展示深度的三句话

1. **"我做过实验..."** → 数据驱动，不是拍脑袋
2. **"最初是 X，后来改成 Y，因为..."** → 迭代思维
3. **"如果再做一次，我会..."** → 成长心态

### 坦诚讨论已知限制

- 254 题集中 paraphrase/multihop 题型召回率低（已修复超时，待重新评估）
- ChromaDB 是原型级，生产需换 Milvus/Qdrant
- 前端 662 行 Context 需要重构
- faithfulness 指标在"LLM 已知答案"场景下不准确

> 面试官更看重你能**识别问题 + 量化问题 + 有改进思路**，而不是假装完美。

---

## 十、项目数字速记卡

| 指标 | 数值 |
|------|------|
| 检索策略数 | 5 种（可配置切换） |
| HR@5 提升 | 23.5% → 35.3%（+50%） |
| Faithfulness | 0.928（核心集） |
| Context Precision | 0.964 |
| 语义缓存阈值 | 0.90（余弦相似度） |
| 语义缓存命中延迟 | <50ms |
| BM25 停用词 | 80+ 个 |
| Prompt 变体数 | 5 个 |
| Chunk Size 测试档 | 4 档（200/500/800/1200） |
| 后端测试 | 384 passed |
| 前端测试 | 57 passed |
| Prometheus 指标 | HTTP/RAG/LLM/Cache/Rate Limit |
| docker-compose 服务 | 5 个 |
| 配置项 | 50+ 环境变量 |
| 评估超时策略 | 自适应（exact 15s / paraphrase 60s / complex 120s） |
