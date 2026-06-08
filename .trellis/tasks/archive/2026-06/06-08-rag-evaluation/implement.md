# RAG 评估体系 — 实施计划

## 1. 实施顺序（5 阶段）

| 阶段 | 内容 | 验证方式 | 依赖 |
|---|---|---|---|
| **Stage 1：基础设施** | `metrics.py` + `regression.py` + `reporter.py`（纯逻辑，不调 API） | pytest 单测 | 无 |
| **Stage 2：智谱适配层** | `zhipu_llm.py` + 验证 RAGAS 接入 | 手动 import + 调通 1 指标 | Stage 1 |
| **Stage 3：评估运行器** | `runner.py`（并发 + 重试 + 单题隔离） | pytest 单测 + 手动 dry-run | Stage 1 |
| **Stage 4：CLI 入口** | `run.py` + 改造 `ragas_eval.py` + `comparison.py` | 手动跑通 + 报告生成 | Stage 2-3 |
| **Stage 5：数据集扩充** | 扩充 `eval_dataset.json` 到 30+ | 文件存在 + 数量正确 | Stage 4 |

---

## 2. Stage 1：基础设施（预计 1-2 小时）

### 2.1 创建 `evaluation/metrics.py`

纯函数实现，不依赖 RAGService / ChromaDB / LLM。

**核心**：
- `hit_rate_at_k(retrieved_ids, relevant_id, k)`
- `mrr(retrieved_ids, relevant_id)`
- `compute_retrieval_metrics(results, k=5)`

### 2.2 创建 `evaluation/regression.py`

**核心**：
- `save_results(summary_dict, results_dir)` — 写 latest.json + history/<ts>.json 备份
- `check_regression(current_metrics, results_dir)` — diff 上次结果，5% 阈值

### 2.3 创建 `evaluation/reporter.py`

**核心**：
- `generate_terminal_summary(summary)` — stdout 输出
- `generate_markdown_report(summary, comparison, output_path)` — 生成 report.md

### 2.4 验证

```bash
cd backend
python -m pytest tests/test_evaluation.py::TestHitRateAtK \
                  tests/test_evaluation.py::TestMRR \
                  tests/test_evaluation.py::TestRegression \
                  tests/test_evaluation.py::TestReporter -v
```

**预期**：所有用例通过（无 API 调用，全本地）。

---

## 3. Stage 2：智谱适配层（预计 30 分钟）

### 3.1 创建 `evaluation/zhipu_llm.py`

```python
from langchain_openai import ChatOpenAI
from app.config import get_settings


def create_zhipu_llm(temperature: float = 0.0, max_tokens: int = 4096) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key=settings.zhipu_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=180,
    )
```

### 3.2 验证 RAGAS 接入

```python
# backend/scripts/verify_ragas.py（一次性脚本，不入版本）
import asyncio
from evaluation.zhipu_llm import create_zhipu_llm
from ragas import evaluate, SingleTurnSample
from ragas.metrics import faithfulness

async def verify():
    llm = create_zhipu_llm()
    sample = SingleTurnSample(
        user_input="什么是 RAG？",
        response="RAG 是检索增强生成。",
        retrieved_contexts=["RAG 是结合检索和生成的 AI 架构。"],
    )
    # RAGAS 0.2+ 改为单样本评估
    from ragas.llms import LangchainLLMWrapper
    metric = faithfulness(llm=LangchainLLMWrapper(llm))
    score = await metric.single_turn_ascore(sample)
    print(f"faithfulness = {score}")

asyncio.run(verify())
```

**注意**：RAGAS 0.2+ 大改了 API（`evaluate()` + `Dataset` → `metric.single_turn_ascore()` + `SingleTurnSample`）。具体接口以安装版本为准。

### 3.3 安装依赖

```bash
cd backend
pip install ragas datasets langchain-openai tenacity
pip freeze | grep -E "ragas|ten|langchain-openai|datasets" >> requirements.txt
```

---

## 4. Stage 3：评估运行器（预计 1-2 小时）

### 4.1 创建 `evaluation/runner.py`

**核心**：
- `EvalResult` / `EvalSummary` dataclass
- `run_concurrent_evaluation(items, evaluate_fn, concurrency=5)`
- `tenacity` 重试装饰器
- `_aggregate_metrics(results)`

### 4.2 单题评估函数原型

```python
async def evaluate_single_ragas(item: dict) -> EvalResult:
    """对单题跑 RAGAS 评估"""
    from app.services.rag_service import RAGService
    rag = RAGService()
    result = await rag.query(item["question"])
    # ... 调 RAGAS metrics ...
    return EvalResult(id=item["id"], success=True, metrics={...})
```

### 4.3 验证

```bash
cd backend
python -m pytest tests/test_evaluation.py::TestAggregateMetrics -v
```

**预期**：聚合逻辑单测通过。

---

## 5. Stage 4：CLI 入口 + 改造现有脚本（预计 2-3 小时）

### 5.1 创建 `evaluation/run.py`

**核心**：
- `argparse` 解析 `--mode` / `--skip-regression` / `--verbose`
- 前置检查（ZHIPU_API_KEY 存在、ChromaDB 可连接）
- 加载 `eval_dataset.json`
- 分发到 `_run_ragas` / `_run_comparison` / `_run_sanity`
- 报告生成 + 回归检测

### 5.2 改造 `evaluation/ragas_eval.py`

**原结构**：单文件，含 `run_evaluation()` + 逻辑
**新结构**：保留入口，逻辑委托给 `runner.py`：

```python
# 旧：
async def run_evaluation():
    # 加载数据 + 调 RAGService + 调 RAGAS + 打印
    ...

# 新：
async def run_evaluation():
    """RAGAS 评估入口（兼容旧调用）"""
    from evaluation.run import _run_ragas_async
    return await _run_ragas_async()
```

**关键改动**：
- 用 `runner.run_concurrent_evaluation` 替代 for 循环
- 用 `reporter.generate_terminal_summary` / `generate_markdown_report` 替代 print
- 用 `regression.save_results` / `check_regression` 替代直接写 JSON

### 5.3 改造 `evaluation/comparison.py`

**关键改动**：
- 用 `metrics.compute_retrieval_metrics` 替代 `overlap > 5`
- 用 `reporter` 替代 print
- 用 `regression` 替代 JSON 写

### 5.4 验证

```bash
cd backend
# 快速验证
python -m evaluation.run --mode sanity
# 完整跑（用真实数据，可能 1-2 分钟）
python -m evaluation.run
# 看报告
cat evaluation/report.md
ls evaluation/results/
```

**预期**：
- 终端打印指标摘要
- `evaluation/report.md` 自动生成
- `evaluation/results/latest.json` + `history/<ts>.json` 存在
- 第二次跑触发回归告警（如果指标波动）

---

## 6. Stage 5：数据集扩充（预计 1-2 小时）

### 6.1 扩充 `evaluation/eval_dataset.json`

从 13 题扩到 30+：
- recall: 12 道（从 `data/raw/*.md` 现有 75 道题中抽）
- paraphrase: 6 道（改写 recall 题的问法）
- cross_category: 6 道（混入其他分类，验证 RAG 不串台）
- irrelevant: 6 道（手工加，如"法国的首都是什么"）

**每题字段**：
```json
{
  "id": "recall_001",
  "type": "recall",
  "question": "...",
  "ground_truth": "...",
  "category": "RAG",
  "source": "questions.md"
}
```

**注意**：每题 ground_truth 从 md 文件直接抽现有答案（不重写）。`id` 字段是新加的，用于回归检测。

### 6.2 验证

```bash
python -c "
import json
data = json.load(open('backend/evaluation/eval_dataset.json'))
print(f'Total: {len(data)}')
from collections import Counter
print(Counter(d['type'] for d in data))
"
```

**预期**：Total >= 30, recall=12, paraphrase=6, cross_category=6, irrelevant=6。

---

## 7. Review Gates（每阶段结束前）

| Gate | 检查 |
|---|---|
| `trellis-before-dev` | 调取 `.trellis/spec/backend/quality-guidelines.md` |
| `trellis-check` | 跑 pytest（不调 API 部分）+ ruff + mypy |
| 手动验证 | `python -m evaluation.run` 跑一次，验证报告生成 |

## 8. 验证命令清单

```bash
# 后端
cd backend
python -m pytest tests/test_evaluation.py -v
python -m pytest tests/ -v  # 全量
python -m ruff check evaluation/
python -m mypy evaluation/

# 手动跑
python -m evaluation.run --mode sanity
python -m evaluation.run
cat evaluation/report.md
```

## 9. 回滚点

| 阶段 | 回滚操作 |
|---|---|
| Stage 1 | 删除 `metrics.py` / `regression.py` / `reporter.py` + `tests/test_evaluation.py` |
| Stage 2 | 删除 `zhipu_llm.py` + `pip uninstall ragas langchain-openai tenacity` |
| Stage 3 | 删除 `runner.py` |
| Stage 4 | 删除 `run.py` + `git checkout ragas_eval.py comparison.py` |
| Stage 5 | `git checkout eval_dataset.json` 恢复 13 题版本 |

**关键**：`app/services/` / `app/api/` / `app/models/` 完全不动，**主应用零风险**。

## 10. 风险点提醒

- **智谱 OpenAI 兼容端点**：偶发 502/超时 → tenacity 重试 + 5 路并发
- **RAGAS API 变化**：0.1.x → 0.2.x 大改 → 用最新版本，metrics 名称变化时自动跳过
- **数据集质量**：扩充时人工校对前 5 题 ground_truth，避免"评估 LLM 用 LLM 生成的答案"
- **ChromaDB 状态**：评估可能读取生产数据 → 不在评估时导入/删除数据
- **智谱 API key 泄露**：报告只存指标，不存 question/answer/ground_truth 明文

## 11. 拆分建议

如时间紧，可拆为 3 个子任务：
1. `eval-01-foundation` — Stage 1+3（metrics + regression + reporter + runner，纯逻辑）
2. `eval-02-zhipu-ragas` — Stage 2+4（智谱适配 + CLI + 改造现有脚本）
3. `eval-03-dataset` — Stage 5（扩充数据集）

子任务用 `task.py add-subtask <parent> <child>` 链接，独立可验证。

## 12. 依赖新增汇总

```txt
# 追加到 backend/requirements.txt（锁版本）
ragas==0.1.21
datasets>=2.14.0,<3.0.0
langchain-openai>=0.1.0
tenacity>=8.2.0
```

需在本地 venv 装好后再跑评估。

## 13. 实施期间 Review 发现的问题（已修正）

| # | 问题 | 修正 |
|---|---|---|
| 1 | `RAGAS 0.2+` 改单题接口，**`asyncio.gather` 不适用** | 锁版本到 0.1.21 走批量接口；并发在 RAGAS 内部 |
| 2 | `comparison.py` plan_a 用 `vector_store.query` 只读 documents，**没 id 字段** | 改造 plan_a 提取 metadata.question_id |
| 3 | `eval_dataset.json` 当前 13 题**没 id 字段**，Hit Rate 无 relevant_id 可对照 | Stage 5 扩充时**必须**加 `id` 字段 |
| 4 | tenacity 重试位置设计在 runner.py，**实际 RAGAS 0.1.x 调 LLM 走内部链路** | 重试装饰器移到 `zhipu_llm.py` 内的 ChatOpenAI 包装层 |
| 5 | `get_db()` 已是单例（`app/core/db.py`），test 共享 fixture 应改用 | fixture 改 `monkeypatch.setattr` 注入临时路径 |
