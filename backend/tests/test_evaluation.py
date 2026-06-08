"""评估系统单元测试

不含 @pytest.mark.eval 的测试默认运行（CI 跑）。
含 @pytest.mark.eval 的测试需显式 -m eval（需 ZHIPU_API_KEY + ChromaDB）。
"""

import pytest

from evaluation.metrics import compute_retrieval_metrics, hit_rate_at_k, mrr, question_match
from evaluation.regression import REGRESSION_THRESHOLD, check_regression, save_results
from evaluation.reporter import generate_markdown_report, generate_terminal_summary


# =========================================================================
# 指标计算（纯逻辑，不调 API）
# =========================================================================


class TestQuestionMatch:
    def test_exact_match(self):
        doc = "题目：什么是 Transformer？\n\n答案：..."
        assert question_match(doc, "什么是 Transformer？") is True

    def test_similar_match(self):
        doc = "题目：请详细解释一下 Transformer 模型中的自注意力机制是如何工作的？\n\n答案：..."
        assert question_match(doc, "Transformer 的自注意力机制是如何工作的？") is True

    def test_no_match(self):
        doc = "题目：什么是 Python 装饰器？\n\n答案：..."
        assert question_match(doc, "Transformer 是什么？") is False

    def test_with_colon_cn(self):
        doc = "题目：什么是位置编码？\n\n答案：..."
        assert question_match(doc, "什么是位置编码？") is True


class TestHitRateAtK:
    def test_hit_at_position_1(self):
        docs = ["题目：请详细解释 Transformer 模型中的自注意力机制是如何工作的\n答案：自注意力通过计算 Q K V 得到权重"]
        assert hit_rate_at_k(docs, "Transformer 的自注意力机制是怎么算的", k=5) is True

    def test_hit_at_position_3(self):
        docs = [
            "题目：什么是 Python 装饰器\n答案：装饰器是一种函数",
            "题目：RAG 的基本流程是什么\n答案：检索增强生成",
            "题目：请解释 Transformer 中的自注意力机制\n答案：自注意力计算 Q K V",
        ]
        assert hit_rate_at_k(docs, "Transformer 的注意力机制", k=5) is True

    def test_miss(self):
        docs = [
            "题目：什么是 Python 装饰器\n答案：装饰器是一种函数",
            "题目：RAG 的基本流程是什么\n答案：检索增强生成",
            "题目：RLHF 的训练流程\n答案：强化学习人类反馈",
        ]
        assert hit_rate_at_k(docs, "MoE 混合专家模型的工作原理", k=5) is False

    def test_hit_beyond_k(self):
        docs = [
            "题目：什么是 Python 装饰器\n答案：装饰器",
            "题目：RAG 的基本流程\n答案：检索增强生成",
            "题目：RLHF 的训练流程\n答案：强化学习",
            "题目：Transformer 的自注意力机制\n答案：自注意力计算",
        ]
        assert hit_rate_at_k(docs, "Transformer 的自注意力机制", k=3) is False

    def test_empty_retrieved(self):
        assert hit_rate_at_k([], "Transformer 自注意力", k=5) is False


class TestMRR:
    def test_rank_1(self):
        docs = ["题目：Transformer 的自注意力机制是如何工作的\n答案：自注意力计算"]
        assert mrr(docs, "Transformer 的注意力机制怎么算") == 1.0

    def test_rank_2(self):
        docs = [
            "题目：什么是 Python 装饰器\n答案：装饰器",
            "题目：Transformer 的自注意力机制\n答案：自注意力计算",
        ]
        assert mrr(docs, "Transformer 的注意力机制") == 0.5

    def test_rank_3(self):
        docs = [
            "题目：Python 装饰器\n答案：装饰器",
            "题目：RAG 流程\n答案：检索增强生成",
            "题目：Transformer 的自注意力机制\n答案：自注意力",
        ]
        assert mrr(docs, "Transformer 的注意力机制") == pytest.approx(1 / 3)

    def test_miss(self):
        docs = [
            "题目：Python 装饰器\n答案：装饰器",
            "题目：RAG 流程\n答案：检索增强生成",
        ]
        assert mrr(docs, "MoE 混合专家模型") == 0.0

    def test_empty(self):
        assert mrr([], "Transformer 自注意力") == 0.0


class TestComputeRetrievalMetrics:
    def test_all_hits(self):
        results = [
            {"retrieved_texts": ["题目：Transformer 的自注意力机制\n答案：A"], "eval_question": "Transformer 的注意力机制怎么算"},
            {"retrieved_texts": ["题目：Python 装饰器\n...", "题目：Transformer 的自注意力机制\n答案：A"], "eval_question": "Transformer 的注意力机制怎么算"},
        ]
        m = compute_retrieval_metrics(results, k=2)
        assert m["hit_rate@2"] == 1.0
        assert m["mrr"] == pytest.approx((1.0 + 0.5) / 2)

    def test_partial_hit(self):
        results = [
            {"retrieved_texts": ["题目：Transformer 的自注意力机制\n答案：A"], "eval_question": "Transformer 的注意力机制怎么算"},
            {"retrieved_texts": ["题目：Python 装饰器\n...", "题目：RAG 流程\n..."], "eval_question": "MoE 混合专家模型"},
        ]
        m = compute_retrieval_metrics(results, k=5)
        assert m["hit_rate@5"] == 0.5
        assert m["mrr"] == pytest.approx((1.0 + 0.0) / 2)

    def test_empty(self):
        m = compute_retrieval_metrics([])
        assert m["hit_rate@5"] == 0.0
        assert m["mrr"] == 0.0

    def test_skips_empty_question(self):
        results = [
            {"retrieved_texts": ["题目：Transformer 的自注意力机制\n答案：A"], "eval_question": "Transformer 的注意力机制怎么算"},
            {"retrieved_texts": ["题目：Transformer 的自注意力机制\n答案：A"], "eval_question": ""},
        ]
        m = compute_retrieval_metrics(results, k=5)
        assert m["hit_rate@5"] == 0.5


# =========================================================================
# 回归检测
# =========================================================================


class TestRegression:
    def test_no_previous(self, tmp_path):
        changes = check_regression({"faithfulness": 0.8}, tmp_path)
        assert changes == []

    def test_no_regression(self, tmp_path):
        save_results({"aggregated": {"faithfulness": 0.8}, "errors": [], "total": 1}, tmp_path)
        changes = check_regression({"faithfulness": 0.82}, tmp_path)
        assert len(changes) == 1
        assert changes[0]["regression"] is False
        assert changes[0]["improvement"] is False

    def test_regression_detected(self, tmp_path):
        save_results({"aggregated": {"faithfulness": 0.8}, "errors": [], "total": 1}, tmp_path)
        changes = check_regression({"faithfulness": 0.7}, tmp_path)
        assert changes[0]["regression"] is True
        assert changes[0]["improvement"] is False

    def test_improvement_detected(self, tmp_path):
        save_results({"aggregated": {"faithfulness": 0.8}, "errors": [], "total": 1}, tmp_path)
        changes = check_regression({"faithfulness": 0.9}, tmp_path)
        assert changes[0]["regression"] is False
        assert changes[0]["improvement"] is True

    def test_within_threshold(self, tmp_path):
        # 波动 < 5% → 不算回归也不算提升
        save_results({"aggregated": {"faithfulness": 0.80}, "errors": [], "total": 1}, tmp_path)
        changes = check_regression({"faithfulness": 0.82}, tmp_path)
        assert changes[0]["regression"] is False
        assert changes[0]["improvement"] is False

    def test_missing_metric_ignored(self, tmp_path):
        save_results({"aggregated": {"faithfulness": 0.8}, "errors": [], "total": 1}, tmp_path)
        changes = check_regression({"answer_relevancy": 0.5}, tmp_path)
        # 旧结果没这个 metric → 跳过
        assert changes == []

    def test_save_creates_history(self, tmp_path):
        save_results({"aggregated": {"f": 0.8}, "errors": [], "total": 1}, tmp_path)
        save_results({"aggregated": {"f": 0.9}, "errors": [], "total": 1}, tmp_path)
        history = list((tmp_path / "history").glob("*.json"))
        assert len(history) == 1  # 第一次的备份
        assert (tmp_path / "latest.json").exists()
        assert (tmp_path / "latest_summary.json").exists()


# =========================================================================
# 报告生成
# =========================================================================


class TestReporter:
    def test_terminal_summary_contains_metrics(self):
        text = generate_terminal_summary(
            aggregated={"faithfulness": 0.85},
            errors=[],
            total=1,
        )
        assert "faithfulness" in text
        assert "0.8500" in text

    def test_terminal_summary_shows_comparison(self):
        text = generate_terminal_summary(
            aggregated={"faithfulness": 0.85},
            errors=[],
            total=1,
            comparison={"A_纯向量": {"hit_rate@5": 0.7, "mrr": 0.6}},
        )
        assert "A_纯向量" in text
        assert "HR@5" in text

    def test_terminal_summary_warns_high_error_rate(self):
        text = generate_terminal_summary(
            aggregated={"faithfulness": 0.5},
            errors=["e1", "e2", "e3"],
            total=5,
        )
        assert "失败率" in text
        assert "60%" in text

    def test_markdown_report_writes_file(self, tmp_path):
        out = tmp_path / "report.md"
        content = generate_markdown_report(
            aggregated={"faithfulness": 0.85, "answer_relevancy": 0.7},
            errors=["bad_1"],
            total=5,
            output_path=out,
        )
        assert out.exists()
        assert "RAG 评估报告" in content
        assert "faithfulness" in content
        assert "bad_1" in content

    def test_markdown_report_with_comparison(self, tmp_path):
        out = tmp_path / "report.md"
        content = generate_markdown_report(
            aggregated={"faithfulness": 0.85},
            errors=[],
            total=1,
            comparison={"A": {"hit_rate@5": 0.7, "mrr": 0.6}},
            output_path=out,
        )
        assert "检索策略对比" in content
        assert "Hit Rate@5" in content
        assert "MRR" in content
