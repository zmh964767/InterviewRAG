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


async def _evaluate_v04(
    ragas_data: dict,
    faithfulness_m,
    answer_relevancy_m,
    context_precision_m,
    context_recall_m,
) -> dict:
    """RAGAS 0.4+ 单题接口 + asyncio.gather 并发

    对每题调 4 个 metric 的 ascore，5 路并发。
    """
    n = len(ragas_data["question"])
    sem = asyncio.Semaphore(2)  # RAGAS metrics 不是线程安全的，限制并发

    async def score_one(idx: int):
        async with sem:
            question = ragas_data["question"][idx]
            answer = ragas_data["answer"][idx]
            contexts = ragas_data["contexts"][idx]

            def _safe_score(result):
                if result is None:
                    return 0.0
                try:
                    return float(result.value) if hasattr(result, 'value') else float(result)
                except Exception:
                    return 0.0

            try:
                f = _safe_score(await faithfulness_m.ascore(question, answer, contexts))
            except Exception as e:
                logger.warning(f"题目 {idx} faithfulness 失败: {e}")
                f = 0.0
            try:
                # AnswerRelevancy.ascore(user_input, response) — 只需要 2 个参数
                a = _safe_score(await answer_relevancy_m.ascore(question, answer))
            except Exception as e:
                logger.warning(f"题目 {idx} answer_relevancy 失败: {e}")
                a = 0.0
            try:
                # ContextPrecision.ascore(user_input, reference, retrieved_contexts)
                cp = _safe_score(await context_precision_m.ascore(question, answer, contexts))
            except Exception as e:
                logger.warning(f"题目 {idx} context_precision 失败: {e}")
                cp = 0.0
            try:
                # ContextRecall.ascore(user_input, retrieved_contexts, reference)
                cr = _safe_score(await context_recall_m.ascore(question, contexts, answer))
            except Exception as e:
                logger.warning(f"题目 {idx} context_recall 失败: {e}")
                cr = 0.0
            return f, a, cp, cr

    results = await asyncio.gather(*[score_one(i) for i in range(n)])

    f_sum = sum(r[0] for r in results) / n if n else 0
    a_sum = sum(r[1] for r in results) / n if n else 0
    cp_sum = sum(r[2] for r in results) / n if n else 0
    cr_sum = sum(r[3] for r in results) / n if n else 0

    return {
        "faithfulness": f_sum,
        "answer_relevancy": a_sum,
        "context_precision": cp_sum,
        "context_recall": cr_sum,
    }


async def run_ragas_evaluation(items: list[dict]) -> EvalSummary:
    """运行 RAGAS 0.1.x 评估

    Args:
        items: 评估题列表 [{id, question, ground_truth, ...}]

    Returns:
        EvalSummary
    """
    from app.services.rag_service import RAGService
    from evaluation.zhipu_llm import create_zhipu_llm

    rag = RAGService()
    llm = create_zhipu_llm()

    # 1. 收集所有题的 (question, answer, contexts, ground_truth)
    ragas_data: dict[str, list] = {
        "question": [], "answer": [], "contexts": [], "ground_truth": [],
    }
    successful_ids: list[str] = []
    errors: list[str] = []

    for item in items:
        try:
            result = await rag.query(item["question"])
            ragas_data["question"].append(item["question"])
            ragas_data["answer"].append(result.get("answer", ""))
            contexts = [
                f"{s.get('question', '')}\n{s.get('answer', '')}"
                for s in result.get("sources", [])
            ]
            ragas_data["contexts"].append(contexts)
            ragas_data["ground_truth"].append(item["ground_truth"])
            successful_ids.append(item.get("id", item["question"][:8]))
        except Exception as e:
            logger.error(f"题目 {item.get('id', '?')} RAG 失败: {e}")
            errors.append(item.get("id", "unknown"))

    if not ragas_data["question"]:
        return EvalSummary(
            results=[EvalResult(id=i, success=False, error="RAG 失败") for i in errors],
            aggregated={},
            errors=errors,
            error_rate=1.0,
        )

    # 2. 构造 Dataset 调 evaluate()（RAGAS 0.1.x 批量接口，内部有并发）
    # 0.4+ 改用 collections 接口 + 单题 asyncio.gather 并发
    try:
        from datasets import Dataset
        try:
            # RAGAS 0.4+ 新接口
            from ragas.metrics.collections import (
                AnswerRelevancy as _AnswerRelevancy,
                ContextPrecision as _ContextPrecision,
                ContextRecall as _ContextRecall,
                Faithfulness as _Faithfulness,
            )
            ragas_v04 = True
        except ImportError:
            # RAGAS 0.1.x 旧接口
            from ragas import evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )
            ragas_v04 = False
    except ImportError as e:
        logger.error(f"缺少 RAGAS 依赖: {e}")
        logger.error("请运行: pip install ragas datasets")
        raise

    eval_dataset = Dataset.from_dict(ragas_data)
    try:
        if ragas_v04:
            # RAGAS 0.4+：单题接口 + asyncio.gather 并发
            from evaluation.zhipu_llm import create_zhipu_client
            openai_client = create_zhipu_client()  # 默认 AsyncOpenAI
            settings = __import__('app.config', fromlist=['get_settings']).get_settings()

            from ragas.llms.base import InstructorModelArgs
            from ragas.llms import llm_factory
            from ragas.embeddings import OpenAIEmbeddings

            ragas_llm = llm_factory(settings.llm_model, client=openai_client)
            ragas_emb = OpenAIEmbeddings(model=settings.embedding_model, client=openai_client)

            # 设置 max_tokens=8192（RAGAS 默认 1024，会导致 faithfulness 输出被截断）
            try:
                ragas_llm.model_args.max_tokens = 8192
                ragas_llm.model_args.temperature = 0.0
            except Exception:
                logger.warning("无法设置 ragas_llm.max_tokens，faithfulness 评估可能被截断")

            faithfulness_m = _Faithfulness(llm=ragas_llm)
            answer_relevancy_m = _AnswerRelevancy(llm=ragas_llm, embeddings=ragas_emb)
            context_precision_m = _ContextPrecision(llm=ragas_llm)
            context_recall_m = _ContextRecall(llm=ragas_llm)

            aggregated = await _evaluate_v04(
                ragas_data, faithfulness_m, answer_relevancy_m,
                context_precision_m, context_recall_m,
            )
        else:
            # RAGAS 0.1.x 批量接口
            from ragas import evaluate
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
    results = [EvalResult(id=i, success=True, metrics={}) for i in successful_ids]
    results += [EvalResult(id=e, success=False) for e in errors]

    return EvalSummary(
        results=results,
        aggregated=aggregated,
        errors=errors,
        error_rate=len(errors) / len(items) if items else 0,
    )


async def run_comparison_evaluation(items: list[dict]) -> dict:
    """运行 5 方案检索对比（含多路 Query 改写）

    Returns:
        {plan_name: {hit_rate@5, mrr}}
    """
    from app.config import get_settings
    from app.core.vectorstore import VectorStore
    from app.rerankers.bge_reranker import BGEReranker
    from app.retrievers.hybrid_retriever import HybridRetriever
    from app.retrievers.multi_query_retriever import MultiQueryRetriever
    from app.retrievers.query_rewriter import QueryRewriter
    from app.retrievers.small_to_big import SmallToBigRetriever
    from app.services.llm_service import LLMService
    from evaluation.metrics import compute_retrieval_metrics

    settings = get_settings()
    vector_store = VectorStore()
    hybrid_retriever = HybridRetriever(vector_store)
    s2b_retriever = SmallToBigRetriever(vector_store)
    reranker = BGEReranker()
    llm_service = LLMService()

    # 方案 E：多路改写 + 混合检索
    rewriter = QueryRewriter(
        llm_service,
        n=settings.multi_query_n,
        timeout_s=settings.multi_query_timeout_s,
    )
    multi_query_retriever = MultiQueryRetriever(
        hybrid_retriever,
        n=settings.multi_query_n,
        top_k=settings.retrieval_top_k,
    )
    multi_query_retriever.set_rewriter(rewriter)

    async def plan_a(question: str) -> dict:
        """方案 A：纯向量检索（baseline）"""
        results = vector_store.query(query_text=question, n_results=5)
        sources = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                meta = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                ids = results.get("ids", [[]])[0] if results.get("ids") else []
                doc_id = meta.get("question_id", ids[i] if i < len(ids) else f"doc_{i}")
                sources.append({"id": doc_id, "text": doc, "score": 1 - results["distances"][0][i]})
        return {"sources": sources}

    async def plan_b(question: str) -> dict:
        """方案 B：混合检索（向量 + BM25）"""
        results = hybrid_retriever.retrieve(query=question, top_k=5)
        return {"sources": results}

    async def plan_c(question: str) -> dict:
        """方案 C：混合检索 + Re-ranking"""
        results = hybrid_retriever.retrieve(query=question, top_k=20)
        # BGE Re-ranker 在 Windows 上加载极慢，单独 try/except 隔离
        try:
            if reranker.is_available():
                results = reranker.rerank(query=question, documents=results, top_k=5)
        except Exception as e:
            logger.warning(f"Re-ranker 失败（plan_c），退回 top-5: {e}")
            results = results[:5]
        return {"sources": results[:5]}

    async def plan_d(question: str) -> dict:
        """方案 D：小块检索 + 大块生成"""
        results = s2b_retriever.retrieve(query=question, top_k=5, n_candidates=20)
        return {"sources": results}

    async def plan_e(question: str) -> dict:
        """方案 E：多路 Query 改写 + 混合检索（去重合并）

        rewriter 失败/超时/空 → 回退单路混合（等同 plan_b 行为）。
        在 async 上下文里直接调 arewrite/aretrieve_with_queries，避免嵌套 event loop。
        """
        try:
            queries = await rewriter.arewrite(question)
            results = await multi_query_retriever.aretrieve_with_queries(queries, top_k=5)
        except Exception as e:
            logger.warning(f"plan_e 多路改写失败，回退单路混合: {e}")
            results = hybrid_retriever.retrieve(query=question, top_k=5)
        return {"sources": results}

    plans = {
        "A_纯向量": plan_a,
        "B_混合检索": plan_b,
        "C_混合+Rerank": plan_c,
        "D_小块检索大块生成": plan_d,
        "E_多路改写混合": plan_e,
    }

    # BGE Re-ranker 在某些环境加载极慢（>5 分钟），先预检一次
    rerank_disabled = False
    try:
        if not reranker.is_available():
            rerank_disabled = True
            logger.warning("BGE Re-ranker 不可用，plan_c 将与 plan_b 退化为相同结果")
    except Exception:
        rerank_disabled = True

    if rerank_disabled:
        plans = {k: v for k, v in plans.items() if k != "C_混合+Rerank"}

    sem = asyncio.Semaphore(CONCURRENCY)

    async def run_plan(name: str, plan_fn):
        async with sem:
            plan_results = []
            for item in items:
                try:
                    r = await plan_fn(item["question"])
                    texts = [s.get("text", "") for s in r.get("sources", []) if isinstance(s, dict)]
                    plan_results.append({
                        "retrieved_texts": texts,
                        "eval_question": item["question"],
                    })
                except Exception as e:
                    logger.error(f"方案 {name} 题目 {item.get('id', '?')} 失败: {e}")
            return name, compute_retrieval_metrics(plan_results, k=5)

    plan_results = await asyncio.gather(*[run_plan(n, f) for n, f in plans.items()])
    return dict(plan_results)
