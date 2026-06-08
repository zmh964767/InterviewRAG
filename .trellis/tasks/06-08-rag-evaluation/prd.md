# RAG 评估体系

## Goal

为现有 RAG 系统建立可重复、可对比的评估体系，回答：
- 检索模块的**当前质量**（哪些查询答得不好）
- 多种检索策略的**横向对比**（向量 vs 混合 vs 混合+Rerank vs 小块检索大块生成）
- **回归检测**——新加题/调参后 RAG 质量是否下降

让"调参"有数据支撑，而不是凭感觉。

## Confirmed Facts（来自代码）

### 已存在能力（[backend/evaluation/](backend/evaluation/)）
- `eval_dataset.json`：13 道题，4 类 — `recall`(5) / `paraphrase`(2) / `cross_category`(4) / `irrelevant`(2)
- `comparison.py`：跑 4 种检索方案（A_纯向量 / B_混合 / C_混合+Rerank / D_小块检索大块生成），用"ground_truth 前 50 字与 top1 文本重叠字符数 > 5"做"准确率"
- `ragas_eval.py`：跑 RAGAS 4 指标 — `faithfulness` / `answer_relevancy` / `context_precision` / `context_recall`
- 两个脚本都通过 `python -m evaluation.ragas_eval` / `python -m evaluation.comparison` 手动跑，结果打印到 stdout + 存到 `*.results.json`

### 已存在但有问题
- ⚠️ `eval_dataset.json` 13 题太少，统计意义弱（`cross_category` 4 题 / `irrelevant` 2 题，样本量都不够）
- ⚠️ `comparison.py` 的"准确率"启发式（`overlap > 5`）非常粗糙，对中文长答案噪声大
- ⚠️ `ragas_eval.py` 调用 `ragas` 库，需要 LLM API（默认 OpenAI，**不接智谱**会失败）
- ⚠️ 两脚本**没有自动化**——`__main__` 里写死路径，CI 不能跑
- ⚠️ 没有**回归检测**机制——历史结果没有存档，无从对比
- ⚠️ 没有**评估结果可视化**（只 print + 存 JSON）
- ⚠️ 评估会污染 ChromaDB（每次 `VectorStore()` 重新 init）

### 已有评估输入数据流
```
eval_dataset.json (静态)
    ↓
[comparison.py] → 4 个 retriever → 关键词重叠 → 打印 + JSON
[ragas_eval.py] → RAGService.query() → RAGAS 4 指标 → 打印 + JSON
```

### 业务约束
- 智谱 LLM API 是唯一的 LLM 通道（不能假设 OpenAI）
- Embedding 也是智谱（评估生成 contexts 时要走智谱 Embedding）
- 评估时间敏感——跑 13 道题 + LLM 调用估计 1-2 分钟

## Scope (用户已选 B 方案)

### In Scope（MVP 范围）
- ✅ 调通 RAGAS 端到端评估（4 指标）
- ✅ 智谱 LLM 适配（RAGAS 默认 OpenAI，走 OpenAI 兼容端点）
- ✅ 评估数据集扩充（13 → 30+）
- ✅ 回归检测（历史结果存档 + 对比）
- ✅ CLI 化（`python -m evaluation.run` 一键跑）
- ✅ 检索层轻量 sanity check（Hit Rate，作为子步骤）

### Out of Scope（MVP 暂不做）
- ❌ 单独 LLM-as-judge（RAGAS 内置 judge 足够）
- ❌ 实时评估
- ❌ 用户反馈闭环
- ❌ 多语种
- ❌ 评估数据自动生成

## Confirmed Decisions

- **目标层级**：B 方案（端到端 RAGAS 4 指标）
- **智谱对接方式**：A 方案（OpenAI 兼容端点 + langchain ChatOpenAI）
- **数据集扩充方式**：D 方案（混合）— 真实题 20 道 + 人工补 10 道边缘 case，总 30+
  - recall: 12 道（从现有 md 抽）
  - paraphrase: 6 道（改写）
  - cross_category: 6 道（混入）
  - irrelevant: 6 道（手工加）
  - 字段新增 `id` 用于回归检测
- **回归检测存档**：B 方案 — `latest.json` + `history/<timestamp>.json` 时间序备份
  - 指标波动 > 5% 触发告警（stderr + exit 1）
  - 不做邮件/slack 通知
- **报表形态**：D 方案 — 终端打印摘要 + 自动生成 `report.md` 详情
  - 表格：整体指标 + 按分类聚合 + top 5 低分题
  - 旧 metric 自动跳过 + warn（不阻断评估）
- **执行入口**：D 方案 — `run.py` CLI + `pytest -m eval` 可调用
  - 模式：`--mode {full,ragas,comparison,sanity}`，默认 `full`
  - 选项：`--skip-regression` / `--verbose`
  - pytest 集成：`@pytest.mark.eval` 标记
- **失败处理**：D 方案 — 单题隔离 + 网络重试
  - 每题包 try/except，失败题记录到 `errors[]` 继续跑
  - 失败题在 report.md 单独列「失败案例」段，**不参与指标计算**
  - LLM/Embedding 调用：tenacity 重试 3 次 + 指数退避（1s/2s/4s）
  - 单题超时：180s（智谱每题 2-3 次 LLM 调用）
  - 失败率 > 20%：告警，但仍写 latest.json
  - ChromaDB 错误 / 缺 ZHIPU_API_KEY：立即终止
- **并发控制**：D 方案 — 异步并发（asyncio.Semaphore(5)）
  - 30 题 ÷ 5 路 ≈ 1 分钟
  - 遇 429 rate-limit：tenacity 自动 sleep + retry
  - 不超智谱 60/min 限速
- **CI 集成**：D 方案 — 本地手动跑 + 留 `pytest -m eval` 入口供未来接入
  - 不做 GitHub Actions / pre-commit（评估耗时 1-3 分钟会卡 CI）
  - 文档说明接入方式（秘钥放 GitHub Secrets）
- **评估与生产 RAG 关系**：A 方案 — 评估走生产 RAGService，不做评估专用配置
  - 端到端测，**调参后能反映真实情况**
  - 不支持 `--retriever` 切换（对比功能在 comparison.py 已实现）
- **comparison 启发式替换**：D 方案 — Hit Rate + MRR 替换"overlap > 5"启发式
  - Hit Rate @K：top-k 是否含 ground_truth 题（0/1）
  - MRR：首个相关结果排名的倒数
  - 4 方案对比：保留 A/B/C/D，输出 Hit Rate@5 + MRR

## Acceptance Criteria

### 评估数据
- [ ] `eval_dataset.json` 至少 30 题，含 4 type（recall/paraphrase/cross_category/irrelevant）
- [ ] 每题有 `id` 字段（用于回归追踪）
- [ ] recall 12 道 + paraphrase 6 道 + cross_category 6 道 + irrelevant 6 道

### 评估执行
- [ ] `python -m evaluation.run` 一键执行完整评估
- [ ] 智谱 LLM 通过 OpenAI 兼容端点接入 RAGAS（`ChatOpenAI(base_url=...)`）
- [ ] 异步并发：asyncio.Semaphore(5)，遇 429 自动重试
- [ ] 单题隔离：失败题记录到 `errors[]` 不阻断
- [ ] 单题超时：180s
- [ ] ChromaDB / 缺 ZHIPU_API_KEY：立即终止

### 评估指标
- [ ] RAGAS 4 指标跑通：faithfulness / answer_relevancy / context_precision / context_recall
- [ ] 旧 metric 自动跳过 + warn
- [ ] `comparison.py` 替换为 Hit Rate@5 + MRR（不再用 "overlap > 5" 启发式）
- [ ] 4 方案对比：纯向量 / 混合 / 混合+Rerank / 小块检索大块生成

### 评估输出
- [ ] 终端打印摘要（指标 + 失败数 + 告警）
- [ ] 自动生成 `report.md`（表格：整体 + 按分类 + top 5 低分题 + 失败案例段）
- [ ] `results/latest.json` + `results/history/<timestamp>.json` 归档
- [ ] 指标波动 > 5%：stderr 告警 + exit 1

### 测试
- [ ] `backend/tests/test_evaluation.py` 标记 `@pytest.mark.eval`
- [ ] pytest 可调 `pytest -m eval`（默认跳过，需 `-m eval` 显式启用）
- [ ] 单测覆盖：报告生成器 / Hit Rate 计算 / MRR 计算 / 回归告警

## Notes

- 复杂度：**Complex**（涉及 RAGAS 集成、智谱 LLM 适配、并发、重试、回归检测）— 需要 `design.md` + `implement.md`
- 关键风险：智谱 OpenAI 兼容端点的稳定性（偶发 502）；RAGAS 版本兼容性
- **RAGAS 版本锁定 0.1.21**（0.2+ API 大改、还在 beta；0.1.21 是稳定终点）
- 依赖：`ragas==0.1.21`、`datasets>=2.14,<3.0`、`tenacity>=8.2`、`langchain-openai>=0.1`
- 智谱 API key 必须有效：跑前 `python -c "from app.config import get_settings; print(get_settings().zhipu_api_key[:8])"` 验证
- **重要前置**：`eval_dataset.json` 每题必须有 `id` 字段（用于 Hit Rate 比对和回归追踪）— 现有 13 题无 id，Stage 5 扩充时一起补
