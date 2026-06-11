"""评估系统单元测试

不含 @pytest.mark.eval 的测试默认运行（CI 跑）。
含 @pytest.mark.eval 的测试需显式 -m eval（需 ZHIPU_API_KEY + ChromaDB）。
"""

import asyncio
from unittest.mock import Mock

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


# =========================================================================
# 多路改写 strategy E（mock LLM + mock hybrid，不打 API）
# =========================================================================


class TestPlanE:
    """验证 comparison.py 新增的 plan_e 走通多路改写+混合检索链路。

    注：comparison.py 用函数内 import 拉组件，单测直接 mock 顶层属性较脆。
    这里用等价链路测试：rewriter + multi_query_retriever 端到端跑通。
    """

    def test_plan_e_equiv_pipeline(self):
        """plan_e 等价链路：rewriter 改写 + multi 合并 → 返回 sources。"""
        from app.retrievers.query_rewriter import QueryRewriter
        from app.retrievers.multi_query_retriever import MultiQueryRetriever

        # mock LLM 返回 3 个变体
        mock_llm = Mock()
        mock_llm.chat.return_value = "TCP 连接建立过程\n为什么需要三次握手\nTCP 三次握手机制"

        rewriter = QueryRewriter(mock_llm, n=3, timeout_s=5.0)
        queries = rewriter.rewrite("TCP 三次握手")
        # 原 query 在第 0 位 + 3 变体 = 共 4 个
        assert queries[0] == "TCP 三次握手"
        assert len(queries) == 4

        # mock hybrid 返回 2 个不同 doc（4 个 queries 各 1 路）
        mock_hybrid = Mock()
        mock_hybrid.retrieve.side_effect = [
            [{"id": "q1", "text": "A", "rrf_score": 0.8}],
            [{"id": "q2", "text": "B", "rrf_score": 0.7}],
            [{"id": "q1", "text": "A", "rrf_score": 0.85}],  # q1 又命中
            [{"id": "q2", "text": "B", "rrf_score": 0.75}],  # q2 又命中
        ]

        multi = MultiQueryRetriever(mock_hybrid, n=4, top_k=5)
        results = multi.retrieve_with_queries(queries, top_k=5)
        # q1 + q2 = 2 个 entry
        assert len(results) == 2
        ids = {d["id"] for d in results}
        assert ids == {"q1", "q2"}
        # q1 命中 2 路 → score 取 max (0.85) + matched_queries 累加
        q1 = next(d for d in results if d["id"] == "q1")
        assert q1["rrf_score"] == 0.85
        assert len(q1["matched_queries"]) == 2

    def test_plan_e_handles_rewriter_failure(self):
        """plan_e: rewriter 失败时回退到原 query 单路，不抛异常。"""
        from app.retrievers.query_rewriter import QueryRewriter
        from app.retrievers.multi_query_retriever import MultiQueryRetriever

        # mock LLM 抛异常 → rewriter 应回退 [query]
        mock_llm = Mock()
        mock_llm.chat.side_effect = Exception("智谱 API 挂了")
        rewriter = QueryRewriter(mock_llm, n=3, timeout_s=1.0)
        queries = rewriter.rewrite("TCP 三次握手")
        # 失败回退到 [原 query] 单路
        assert queries == ["TCP 三次握手"]

        # multi 用单路也能跑
        mock_hybrid = Mock()
        mock_hybrid.retrieve.return_value = [
            {"id": "q1", "text": "A", "rrf_score": 0.8}
        ]
        multi = MultiQueryRetriever(mock_hybrid, n=3, top_k=5)
        results = multi.retrieve_with_queries(queries, top_k=5)
        assert len(results) == 1
