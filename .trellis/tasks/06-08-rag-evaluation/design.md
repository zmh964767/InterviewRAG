# RAG 评估体系 — 技术设计

## 1. 架构总览

### 1.1 模块划分

```
backend/evaluation/
├── __init__.py
├── eval_dataset.json          # 评估数据集（30+ 题，已有 13 题需扩充）
├── run.py                     # CLI 入口（新增）
├── runner.py                  # 评估运行器（新增：并发引擎 + 单题隔离 + 重试）
├── metrics.py                 # 检索指标计算（新增：Hit Rate / MRR）
├── zhipu_llm.py               # 智谱 LLM 适配层（新增：ChatOpenAI 包装）
├── reporter.py                # 报告生成器（新增：Markdown + 终端摘要）
├── regression.py              # 回归检测（新增：latest.json diff）
├── ragas_eval.py              # 改造：用新 runner 替换原逻辑
├── comparison.py              # 改造：用 Hit Rate/MRR 替换 overlap 启发式
├── results/                   # 结果目录（新增）
│   ├── latest.json
│   ├── latest_summary.json
│   └── history/
│       └── 2026-06-08T11-30-22.json
└── report.md                  # 自动生成的 Markdown 报告

backend/tests/
└── test_evaluation.py         # pytest 集成（新增）
```

### 1.2 数据流

```
python -m evaluation.run
    │
    ├─ [1] 前置检查：ZHIPU_API_KEY 有效？ChromaDB 有数据？
    │      └─ 失败 → 立即终止 + 提示
    │
    ├─ [2] 加载 eval_dataset.json（30+ 题）
    │
    ├─ [3] 评估模式分发（--mode）
    │      ├─ full / ragas  → RAGAS 端到端评估（一次喂全部题，内部并发）
    │      ├─ full / comparison → 4 方案检索对比（每方案跑一遍所有题）
    │      └─ full / sanity → 检索层快速 check（仅 plan_b hybrid）
    │
    ├─ [4] RAGAS 评估流程
    │      ├─ 一次性收集所有题的 (question, answer, contexts, ground_truth)
    │      ├─ 构造 ragas.Dataset，调 evaluate()（RAGAS 内部并发）
    │      ├─ 4 指标：faithfulness / answer_relevancy / context_precision / context_recall
    │      └─ 重试在 LLM 包装层 tenacity 包好（evaluator_llm 装饰 retry）
    │
    ├─ [5] Comparison 流程（同步，4 方案各跑 30 题）
    │      ├─ plan_a 修复：从 ChromaDB metadata 提取 id（当前只读 documents）
    │      └─ 每题：retrieve() → retrieved_ids 列表 → Hit Rate / MRR
    │
    ├─ [6] 报告生成
    │      ├─ terminal summary（stdout）
    │      ├─ results/latest.json + history/ 归档
    │      └─ report.md（Markdown 表格）
    │
    └─ [7] 回归检测
           ├─ 读 latest.json（上一次结果）
           ├─ diff 本次 vs 上次
           └─ 任一指标波动 > 5% → stderr 告警 + exit 1
```

## 2. 智谱 LLM 适配层

### 2.1 设计：`zhipu_llm.py`

RAGAS 内部通过 langchain 调用 LLM judge。最小改动方案：用 `langchain_openai.ChatOpenAI` 配智谱 OpenAI 兼容端点。

```python
"""智谱 LLM 适配层

将智谱 GLM API 包装为 langchain ChatOpenAI，
供 RAGAS 评估的 LLM judge 使用。
"""

from langchain_openai import ChatOpenAI
from app.config import get_settings


def create_zhipu_llm(
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """创建智谱 LLM 实例（OpenAI 兼容模式）

    Args:
        temperature: 0.0 保证评估结果可复现
        max_tokens: RAGAS judge 需要较长输出

    Returns:
        配置好的 ChatOpenAI 实例
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key=settings.zhipu_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=180,  # 单次 LLM 调用最长 180s
    )
```

**要点**：
- `temperature=0.0`：RAGAS judge 要求确定性输出
- `base_url`：智谱官方 OpenAI 兼容端点
- `timeout=180`：防止长时间等待

### 2.2 RAGAS 集成

```python
# 在 ragas_eval.py 中
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

llm = create_zhipu_llm()
result = evaluate(
    dataset=eval_dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=llm,
)
```

**降级策略**：如果 `langchain_openai` 未安装，fallback 到 `langchain_community.ChatZhipuAI`（需确认该类存在）。如果都没有，报错提示 `pip install langchain-openai`。

## 3. 评估运行器

### 3.1 设计：`runner.py`

**RAGAS 0.1.x 走 `evaluate(dataset, metrics)` 一次性喂入**，RAGAS 内部有并发控制（自带线程池）。**本模块不引入 `asyncio.gather`**——和 RAGAS 0.1.x 模式不匹配。

并发控制**只在 comparison 模式**用（4 方案各跑所有题，可以并发），通过简单 `asyncio.Semaphore` 控制。

```python
"""评估运行器

包装 RAGAS 0.1.x evaluate() 调用，提供单题隔离和重试。
"""

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CONCURRENCY = 4  # 智谱 60/min rate limit 留余量


@dataclass
class EvalResult:
    """单题评估结果"""
    id: str
    success: bool
    metrics: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class EvalSummary:
    """评估总结果"""
    results: list[EvalResult]
    aggregated: dict
    errors: list[str]
    error_rate: float

    @property
    def has_regression_risk(self) -> bool:
        return self.error_rate > 0.2


async def run_ragas_evaluation(items: list[dict]) -> EvalSummary:
    """运行 RAGAS 0.1.x 评估

    Args:
        items: 评估题列表 [{id, question, ground_truth, ...}]

    Returns:
        EvalSummary（aggregated 来自 RAGAS 全局指标，errors 来自异常题）
    """
    from app.services.rag_service import RAGService
    from evaluation.zhipu_llm import create_zhipu_llm

    rag = RAGService()
    llm = create_zhipu_llm()

    # 1. 收集所有题的 (question, answer, contexts, ground_truth)
    successes: list[EvalResult] = []
    errors: list[str] = []
    ragas_data: dict[str, list] = {
        "question": [], "answer": [], "contexts": [], "ground_truth": [],
    }

    # 串行调 RAG（避免智谱并发限流）
    for item in items:
        try:
            result = await rag.query(item["question"])
            ragas_data["question"].append(item["question"])
            ragas_data["answer"].append(result["answer"])
            ragas_data["contexts"].append(
                [s.get("question", "") + " " + s.get("answer", "")
                 for s in result.get("sources", [])]
            )
            ragas_data["ground_truth"].append(item["ground_truth"])
        except Exception as e:
            logger.error(f"题目 {item.get('id', '?')} RAG 失败: {e}")
            errors.append(item.get("id", "unknown"))

    if not ragas_data["question"]:
        return EvalSummary(results=[], aggregated={}, errors=errors, error_rate=1.0)

    # 2. 构造 Dataset 调 evaluate()
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness, answer_relevancy, context_precision, context_recall,
    )

    eval_dataset = Dataset.from_dict(ragas_data)
    try:
        result = evaluate(
            dataset=eval_dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=llm,
        )
        aggregated = {k: float(v) for k, v in result.items()}
    except Exception as e:
        logger.error(f"RAGAS 评估失败: {e}", exc_info=True)
        return EvalSummary(
            results=[EvalResult(id=i, success=False, error=str(e)) for i in errors],
            aggregated={},
            errors=errors,
            error_rate=1.0,
        )

    # 3. 构造 results（每题一个 stub 成功结果）
    for q in ragas_data["question"]:
        successes.append(EvalResult(id=q[:8], success=True, metrics={}))

    return EvalSummary(
        results=successes + [EvalResult(id=e, success=False) for e in errors],
        aggregated=aggregated,
        errors=errors,
        error_rate=len(errors) / len(items),
    )
```

**重要差异**（vs 上版）：
- RAGAS 0.1.x 是**批量接口**，单题隔离在更外层做
- 失败题（`RAG` 阶段就失败）从数据集剔除，不参与 RAGAS 计算
- 串行调 RAG 避免智谱并发限流
- 4 指标由 RAGAS 内部并发

### 3.2 tenacity 重试位置

`zhipu_llm.py` 内的 `ChatOpenAI` 实例**通过 `requests` 走 HTTP**，**tenacity 装饰在 `zhipu_llm.py` 的 LLM 调用层**：

```python
# zhipu_llm.py 内部
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
)
def create_zhipu_llm() -> ChatOpenAI:
    # ChatOpenAI 内部的 .invoke() 会自动重试（包装到 RAGAS evaluator）
    ...
```

**实际 RAGAS 调 LLM 时**：tenacity 在 RAGAS 内部 prompt 解析失败时**不会重试**——这种错误是 schema 不匹配，需要修代码。**只对网络/超时重试**。

### 3.3 Comparison 并发

`comparison.py` 改造时新增并发版（4 方案同时跑）：

```python
async def run_comparison_concurrent(items):
    sem = asyncio.Semaphore(CONCURRENCY)
    plans = {"A_纯向量": plan_a, "B_混合": plan_b, "C_混合+Rerank": plan_c, "D_小块检索": plan_d}

    async def run_plan(name, plan_fn):
        async with sem:
            results = []
            for item in items:
                try:
                    r = await plan_fn(item["question"])
                    ids = [s.get("id", "") for s in r.get("sources", [])]
                    results.append({"retrieved_ids": ids, "relevant_id": item.get("id", "")})
                except Exception as e:
                    logger.error(f"方案 {name} 题目 {item.get('id')} 失败: {e}")
            return name, compute_retrieval_metrics(results, k=5)

    plan_results = await asyncio.gather(*[run_plan(n, f) for n, f in plans.items()])
    return dict(plan_results)
```

## 4. 检索指标

### 4.1 设计：`metrics.py`

替换 `comparison.py` 里的 `overlap > 5` 启发式。

```python
"""检索质量指标

Hit Rate@K 和 MRR 的计算。
"""

def hit_rate_at_k(retrieved_ids: list[str], relevant_id: str, k: int = 5) -> bool:
    """top-k 中是否包含相关文档

    Args:
        retrieved_ids: 检索结果 id 列表（按相关度排序）
        relevant_id: ground_truth 对应的题目 id
        k: 截断数

    Returns:
        True if relevant_id in retrieved_ids[:k]
    """
    return relevant_id in retrieved_ids[:k]


def mrr(retrieved_ids: list[str], relevant_id: str) -> float:
    """Mean Reciprocal Rank（单题版）

    如果相关文档排第 1 → 1.0
    排第 2 → 0.5
    排第 3 → 0.33
    不在结果中 → 0.0
    """
    try:
        rank = retrieved_ids.index(relevant_id) + 1  # 1-based
        return 1.0 / rank
    except ValueError:
        return 0.0


def compute_retrieval_metrics(
    results: list[dict],
    k: int = 5,
) -> dict:
    """批量计算检索指标

    Args:
        results: [{"retrieved_ids": [...], "relevant_id": "..."}, ...]
        k: Hit Rate 截断数

    Returns:
        {"hit_rate@k": float, "mrr": float}
    """
    if not results:
        return {"hit_rate@k": 0.0, "mrr": 0.0}

    hr_sum = sum(hit_rate_at_k(r["retrieved_ids"], r["relevant_id"], k) for r in results)
    mrr_sum = sum(mrr(r["retrieved_ids"], r["relevant_id"]) for r in results)

    n = len(results)
    return {
        f"hit_rate@{k}": hr_sum / n,
        "mrr": mrr_sum / n,
    }
```

### 4.2 comparison.py 改造

原 `comparison.py` 的 4 方案逻辑不变，**修复 plan_a + 替换准确率计算**：

**plan_a 修复**（[comparison.py:40-47](backend/evaluation/comparison.py) 当前只读 `documents`，没 id）：

```python
async def plan_a(question: str) -> dict:
    """方案 A：纯向量检索（baseline）"""
    results = vector_store.query(query_text=question, n_results=5)
    sources = []
    if results and results.get("documents"):
        # documents / metadatas / ids 是平行数组
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            doc_id = meta.get("question_id", results.get("ids", [[]])[0][i] if results.get("ids") else f"doc_{i}")
            sources.append({"id": doc_id, "text": doc, "score": 1 - results["distances"][0][i]})
    return {"sources": sources}
```

**准确率计算替换**：

```python
# 旧：overlap > 5
# 新：
from evaluation.metrics import compute_retrieval_metrics

# 每方案收集 retrieved_ids
plan_results = []
for item in eval_items:
    result = await plan_func(item["question"])
    retrieved_ids = [s.get("id", "") for s in result.get("sources", [])]
    plan_results.append({
        "retrieved_ids": retrieved_ids,
        "relevant_id": item.get("id", ""),  # 用 item.id 不用 ground_truth 文本
    })

metrics = compute_retrieval_metrics(plan_results, k=5)
# → {"hit_rate@5": 0.83, "mrr": 0.72}
```

**注意**：`relevant_id` 用 `item["id"]`（题目 id），不是 `item["ground_truth"]`（答案文本）。前提是 `eval_dataset.json` 每题都有 `id` 字段。

## 5. 报告生成器

### 5.1 设计：`reporter.py`

生成两份输出：终端摘要 + `report.md`。

```python
"""评估报告生成器"""

import json
from datetime import datetime
from pathlib import Path


def generate_terminal_summary(summary, comparison_results=None) -> str:
    """终端打印摘要"""
    lines = []
    lines.append("=" * 60)
    lines.append("RAG 评估摘要")
    lines.append("=" * 60)

    if summary.aggregated:
        for metric, value in summary.aggregated.items():
            lines.append(f"  {metric:25s}: {value:.4f}")

    lines.append(f"  {'成功题数':25s}: {len(summary.results) - len(summary.errors)}")
    lines.append(f"  {'失败题数':25s}: {len(summary.errors)}")

    if summary.has_regression_risk:
        lines.append(f"\n  ⚠️  失败率 > 20%，结果可能不可靠")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(
    summary,
    comparison_results=None,
    output_path: Path = None,
) -> str:
    """生成 Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# RAG 评估报告 — {now}", ""]

    # 整体指标表格
    if summary.aggregated:
        lines.append("## 整体指标")
        lines.append("")
        lines.append("| 指标 | 分值 |")
        lines.append("|---|---|")
        for metric, value in summary.aggregated.items():
            lines.append(f"| {metric} | {value:.4f} |")
        lines.append("")

    # 检索对比（如有）
    if comparison_results:
        lines.append("## 检索策略对比")
        lines.append("")
        lines.append("| 方案 | Hit Rate@5 | MRR |")
        lines.append("|---|---|---|")
        for plan_name, metrics in comparison_results.items():
            hr = metrics.get("hit_rate@5", 0)
            mrr_val = metrics.get("mrr", 0)
            lines.append(f"| {plan_name} | {hr:.4f} | {mrr_val:.4f} |")
        lines.append("")

    # 失败案例
    if summary.errors:
        lines.append(f"## 失败案例（{len(summary.errors)} 道）")
        lines.append("")
        for err_id in summary.errors:
            lines.append(f"- `{err_id}`")
        lines.append("")

    content = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    return content
```

## 6. 回归检测

### 6.1 设计：`regression.py`

```python
"""回归检测

比较本次评估结果与历史结果，检测指标波动。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

REGRESSION_THRESHOLD = 0.05  # 5% 波动阈值


def save_results(summary_dict: dict, results_dir: Path) -> None:
    """保存结果到 latest.json + history/"""
    results_dir.mkdir(parents=True, exist_ok=True)
    history_dir = results_dir / "history"
    history_dir.mkdir(exist_ok=True)

    # 1. 如果 latest.json 已存在，备份到 history/
    latest_path = results_dir / "latest.json"
    if latest_path.exists():
        timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
        backup = history_dir / f"{timestamp}.json"
        shutil.copy2(latest_path, backup)

    # 2. 写入 latest.json
    latest_path.write_text(
        json.dumps(summary_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 3. 写入 latest_summary.json（仅指标，不含每题明细）
    summary_path = results_dir / "latest_summary.json"
    summary_only = {
        "metrics": summary_dict.get("aggregated", {}),
        "error_count": len(summary_dict.get("errors", [])),
        "total": summary_dict.get("total", 0),
        "timestamp": datetime.now().isoformat(),
    }
    summary_path.write_text(
        json.dumps(summary_only, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def check_regression(
    current_metrics: dict,
    results_dir: Path,
) -> list[dict]:
    """比较本次与上一次结果

    Returns:
        [{"metric": str, "old": float, "new": float, "change": float, "regression": bool}, ...]
    """
    latest_path = results_dir / "latest.json"
    if not latest_path.exists():
        return []

    previous = json.loads(latest_path.read_text(encoding="utf-8"))
    previous_metrics = previous.get("aggregated", {})

    changes = []
    for metric, new_val in current_metrics.items():
        old_val = previous_metrics.get(metric)
        if old_val is None:
            continue
        change = new_val - old_val
        changes.append({
            "metric": metric,
            "old": round(old_val, 4),
            "new": round(new_val, 4),
            "change": round(change, 4),
            "regression": change < -REGRESSION_THRESHOLD,
            "improvement": change > REGRESSION_THRESHOLD,
        })

    return changes
```

## 7. pytest 集成

### 7.1 conftest.py 标记

```python
# backend/tests/conftest.py 追加

def pytest_configure(config):
    config.addinivalue_line("markers", "eval: RAG 评估测试（需 ZHIPU_API_KEY + 数据）")
```

### 7.2 test_evaluation.py

```python
"""评估系统单元测试

不含 @pytest.mark.eval 的测试在 CI 默认运行。
含 @pytest.mark.eval 的测试需显式 -m eval。
"""

import pytest
from evaluation.metrics import hit_rate_at_k, mrr, compute_retrieval_metrics
from evaluation.regression import check_regression, save_results
from evaluation.reporter import generate_terminal_summary, generate_markdown_report
from evaluation.runner import EvalResult, EvalSummary, _aggregate_metrics


# =========================================================================
# 指标计算（纯逻辑，不调 API）
# =========================================================================


class TestHitRateAtK:
    def test_hit_at_1(self):
        assert hit_rate_at_k(["a", "b", "c"], "a", k=5) is True

    def test_hit_at_3(self):
        assert hit_rate_at_k(["x", "y", "a"], "a", k=5) is True

    def test_miss(self):
        assert hit_rate_at_k(["x", "y", "z"], "a", k=5) is False

    def test_hit_beyond_k(self):
        # 排第 4 但 k=3 → miss
        assert hit_rate_at_k(["x", "y", "z", "a"], "a", k=3) is False


class TestMRR:
    def test_rank_1(self):
        assert mrr(["a", "b", "c"], "a") == 1.0

    def test_rank_2(self):
        assert mrr(["x", "a", "b"], "a") == 0.5

    def test_rank_3(self):
        assert mrr(["x", "y", "a"], "a") == pytest.approx(1 / 3)

    def test_miss(self):
        assert mrr(["x", "y", "z"], "a") == 0.0


class TestComputeRetrievalMetrics:
    def test_all_hits(self):
        results = [
            {"retrieved_ids": ["a", "b"], "relevant_id": "a"},
            {"retrieved_ids": ["b", "a"], "relevant_id": "a"},
        ]
        m = compute_retrieval_metrics(results, k=2)
        assert m["hit_rate@2"] == 1.0
        assert m["mrr"] == pytest.approx((1.0 + 0.5) / 2)

    def test_empty(self):
        assert compute_retrieval_metrics([]) == {"hit_rate@5": 0.0, "mrr": 0.0}


# =========================================================================
# 回归检测
# =========================================================================


class TestRegression:
    def test_no_previous(self, tmp_path):
        changes = check_regression({"faithfulness": 0.8}, tmp_path)
        assert changes == []

    def test_no_regression(self, tmp_path):
        save_results({"aggregated": {"faithfulness": 0.8}}, tmp_path)
        changes = check_regression({"faithfulness": 0.82}, tmp_path)
        assert len(changes) == 1
        assert changes[0]["regression"] is False

    def test_regression_detected(self, tmp_path):
        save_results({"aggregated": {"faithfulness": 0.8}}, tmp_path)
        changes = check_regression({"faithfulness": 0.7}, tmp_path)
        assert changes[0]["regression"] is True

    def test_improvement_detected(self, tmp_path):
        save_results({"aggregated": {"faithfulness": 0.8}}, tmp_path)
        changes = check_regression({"faithfulness": 0.9}, tmp_path)
        assert changes[0]["improvement"] is True


# =========================================================================
# 聚合
# =========================================================================


class TestAggregateMetrics:
    def test_basic(self):
        results = [
            EvalResult(id="1", success=True, metrics={"a": 0.8}),
            EvalResult(id="2", success=True, metrics={"a": 0.6}),
        ]
        agg = _aggregate_metrics(results)
        assert agg["a"] == pytest.approx(0.7)

    def test_empty(self):
        assert _aggregate_metrics([]) == {}


# =========================================================================
# 报告生成
# =========================================================================


class TestReporter:
    def test_terminal_summary(self):
        summary = EvalSummary(
            results=[EvalResult(id="1", success=True, metrics={"f": 0.8})],
            aggregated={"f": 0.8},
            errors=[],
            error_rate=0.0,
        )
        text = generate_terminal_summary(summary)
        assert "f" in text
        assert "0.8" in text

    def test_markdown_report(self, tmp_path):
        summary = EvalSummary(
            results=[],
            aggregated={"faithfulness": 0.85},
            errors=["bad_1"],
            error_rate=0.1,
        )
        report = generate_markdown_report(summary, output_path=tmp_path / "report.md")
        assert "faithfulness" in report
        assert "bad_1" in report
        assert (tmp_path / "report.md").exists()


# =========================================================================
# 端到端评估（需真实 API，标记 eval）
# =========================================================================


@pytest.mark.eval
class TestRagAsEvaluation:
    """端到端 RAGAS 评估（需 ZHIPU_API_KEY + ChromaDB 数据）"""

    @pytest.fixture
    def eval_items(self):
        import json
        from pathlib import Path
        path = Path(__file__).parent.parent / "evaluation" / "eval_dataset.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in data if item.get("type") != "irrelevant"]

    def test_ragas_runs_without_error(self, eval_items):
        """验证 RAGAS 4 指标跑通（至少 1 题）"""
        if not eval_items:
            pytest.skip("空数据集")
        from evaluation.ragas_eval import run_evaluation_sync
        result = run_evaluation_sync(eval_items[:1])  # 只跑 1 题
        assert "faithfulness" in result.aggregated or len(result.errors) > 0
```

## 8. CLI 入口：`run.py`

```python
"""评估 CLI 入口

用法：
  python -m evaluation.run                    # 完整评估
  python -m evaluation.run --mode ragas       # 只跑 RAGAS
  python -m evaluation.run --mode comparison  # 只跑检索对比
  python -m evaluation.run --mode sanity      # 快速 sanity check
  python -m evaluation.run --skip-regression  # 跳过回归检测
  python -m evaluation.run --verbose          # 详细输出
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="RAG 评估工具")
    parser.add_argument(
        "--mode",
        choices=["full", "ragas", "comparison", "sanity"],
        default="full",
        help="评估模式",
    )
    parser.add_argument("--skip-regression", action="store_true", help="跳过回归检测")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s | %(message)s")

    # 前置检查
    from app.config import get_settings
    settings = get_settings()
    if not settings.zhipu_api_key:
        print("❌ 缺少 ZHIPU_API_KEY，请在 .env 中配置", file=sys.stderr)
        sys.exit(1)

    # 加载数据集
    eval_path = Path(__file__).parent / "eval_dataset.json"
    if not eval_path.exists():
        print(f"❌ 数据集不存在: {eval_path}", file=sys.stderr)
        sys.exit(1)

    import json
    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    eval_items = [item for item in eval_data if item.get("type") != "irrelevant"]

    logger.info(f"加载 {len(eval_items)} 道评估题（模式: {args.mode}）")

    # 执行评估
    results_dir = Path(__file__).parent / "results"

    if args.mode in ("full", "ragas"):
        summary = asyncio.run(_run_ragas(eval_items))
        _print_terminal(summary)
        _save_and_check_regression(summary, results_dir, args.skip_regression)

    if args.mode in ("full", "comparison"):
        comparison = asyncio.run(_run_comparison(eval_items))
        _print_comparison(comparison)

    if args.mode == "sanity":
        _run_sanity(eval_items)

    logger.info("评估完成")


if __name__ == "__main__":
    main()
```

## 9. 关键文件清单

| 文件 | 类型 | 风险 |
|---|---|---|
| `evaluation/run.py` | 新增 | 低 |
| `evaluation/runner.py` | 新增 | 中（并发逻辑） |
| `evaluation/metrics.py` | 新增 | 低（纯计算） |
| `evaluation/zhipu_llm.py` | 新增 | 中（智谱兼容性） |
| `evaluation/reporter.py` | 新增 | 低 |
| `evaluation/regression.py` | 新增 | 低 |
| `evaluation/eval_dataset.json` | 扩充 | 低 |
| `evaluation/ragas_eval.py` | 改造 | 中 |
| `evaluation/comparison.py` | 改造 | 中 |
| `tests/test_evaluation.py` | 新增 | 低 |
| `requirements.txt` | 扩充 | 低 |
| `tests/conftest.py` | 微调 | 低 |

## 10. 依赖

**锁版本**（避免 RAGAS API 不稳定）：

```txt
# 追加到 backend/requirements.txt
ragas==0.1.21
datasets>=2.14.0,<3.0.0
langchain-openai>=0.1.0
tenacity>=8.2.0
```

**选 0.1.21 的原因**：
- 0.1.x 是稳定线（`evaluate(dataset)` 批量接口）
- 0.2.x 大改 API（`single_turn_ascore`），**还在 beta**
- 0.1.21 是 0.1.x 的最后一个稳定版
- 锁版本避免未来升级引入 breaking change

已有（不动）：
```
chromadb, zhipuai, rank_bm25, sentence-transformers
```

## 11. 回滚策略

**评估模块完全独立**，不改动 `app/services/`、`app/api/`、`app/models/`。回滚方式：

1. 删除 `evaluation/run.py`、`runner.py`、`metrics.py`、`zhipu_llm.py`、`reporter.py`、`regression.py`
2. `git checkout` 恢复 `ragas_eval.py`、`comparison.py`
3. 主应用不受影响

## 12. 风险点

| 风险 | 缓解 |
|---|---|
| 智谱 OpenAI 兼容端点不稳定 | tenacity 重试 3 次 + 退避 |
| RAGAS 版本 API 变化 | metrics 自动跳过 + warn |
| 评估数据集 ground_truth 质量 | 人工校准前 5 题，后续持续扩充 |
| 智谱 API rate limit | Semaphore(5) + 429 重试 |
| 评估时 ChromaDB 被生产数据污染 | 用独立 collection 或快照 |
