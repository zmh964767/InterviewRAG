"""评估运行器

包装 RAGAS 0.1.x evaluate() 调用，提供单题隔离和重试。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONCURRENCY = 4  # 智谱 60/min rate limit 留余量
RAGAS_CHECKPOINT_PATH = Path(__file__).parent / "_ragas_checkpoint.json"


class TokenBucket:
    """简单令牌桶限流（智谱 60 req/min）"""

    def __init__(self, rate_per_min: int = 55, capacity: int | None = None):
        self.rate = rate_per_min / 60.0  # tokens per second
        self.capacity = capacity or rate_per_min
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: int = 1):
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_refill = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                wait = (n - self.tokens) / self.rate
                await asyncio.sleep(wait)


# 全局 RAGAS 限流桶：40 req/min（智谱 60/min 扣除 4 题并行 + 3 次重试的 burst 余量）
ragas_rate_limiter = TokenBucket(rate_per_min=40)


@dataclass
class EvalResult:
    """单题评估结果"""
    id: str
    success: bool
    question: str = ""
    answer: str = ""
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
    progress_callback=None,
    phase_offset=0,
    phase_total=1,
) -> dict:
    """RAGAS 0.4+ 单题接口 + asyncio.gather 并发

    对每题的 4 个 metric 用 asyncio.gather 并发跑（同一 item 的 4 个 LLM 调用并发）。
    跨题用 Semaphore 限速（智谱 60/min）。
    """
    n = len(ragas_data["question"])
    # 智谱 60/min rate limit。Semaphore(2) + 4 指标并行 + RAGAS 内部 3 次重试 ≈ 8-12 LLM calls/in flight。
    # 限流桶 40/min 留出 burst 余量。
    sem = asyncio.Semaphore(2)
    completed = [0]  # mutable counter for logging

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

            # 4 个 metric 并行跑：每个 LLM 调用前申请 1 个 token
            async def _faithfulness():
                await ragas_rate_limiter.acquire(1)
                try:
                    return _safe_score(await faithfulness_m.ascore(question, answer, contexts))
                except Exception as e:
                    logger.warning(f"题目 {idx} faithfulness 失败: {e}")
                    return 0.0

            async def _answer_relevancy():
                await ragas_rate_limiter.acquire(1)
                try:
                    return _safe_score(await answer_relevancy_m.ascore(question, answer))
                except Exception as e:
                    logger.warning(f"题目 {idx} answer_relevancy 失败: {e}")
                    return 0.0

            async def _context_precision():
                await ragas_rate_limiter.acquire(1)
                try:
                    return _safe_score(await context_precision_m.ascore(question, answer, contexts))
                except Exception as e:
                    logger.warning(f"题目 {idx} context_precision 失败: {e}")
                    return 0.0

            async def _context_recall():
                await ragas_rate_limiter.acquire(1)
                try:
                    return _safe_score(await context_recall_m.ascore(question, contexts, answer))
                except Exception as e:
                    logger.warning(f"题目 {idx} context_recall 失败: {e}")
                    return 0.0

            f, a, cp, cr = await asyncio.gather(
                _faithfulness(), _answer_relevancy(),
                _context_precision(), _context_recall(),
            )
            return f, a, cp, cr

    async def tracked_score(idx):
        r = await score_one(idx)
        completed[0] += 1
        if progress_callback:
            progress_callback(phase_offset + completed[0], phase_total)
        return r

    all_scores = await asyncio.gather(*[tracked_score(i) for i in range(n)])

    f_sum = sum(r[0] for r in all_scores) / n if n else 0
    a_sum = sum(r[1] for r in all_scores) / n if n else 0
    cp_sum = sum(r[2] for r in all_scores) / n if n else 0
    cr_sum = sum(r[3] for r in all_scores) / n if n else 0

    aggregated = {
        "faithfulness": f_sum,
        "answer_relevancy": a_sum,
        "context_precision": cp_sum,
        "context_recall": cr_sum,
    }
    per_item = [
        {"faithfulness": r[0], "answer_relevancy": r[1], "context_precision": r[2], "context_recall": r[3]}
        for r in all_scores
    ]
    return aggregated, per_item


async def run_ragas_evaluation(items: list[dict], progress_callback=None) -> EvalSummary:
    """运行 RAGAS 评估

    Args:
        items: 评估题列表 [{id, question, ground_truth, ...}]
        progress_callback: 可选回调 (done, total) 用于进度更新

    Returns:
        EvalSummary
    """
    from app.services.rag_service import RAGService
    from evaluation.zhipu_llm import create_zhipu_llm

    ragas_total = len(items) * 2  # RAG查询 + RAGAS评估 各17步
    rag = RAGService()
    llm = create_zhipu_llm()

    # 1. 收集所有题的 (question, answer, contexts, ground_truth)
    #    使用 semaphore 限制并发 + asyncio.wait_for 超时保护，避免单题卡死
    ragas_data: dict[str, list] = {
        "question": [], "answer": [], "contexts": [], "ground_truth": [],
    }
    successful_ids: list[str] = []
    errors: list[str] = []
    answers_map: dict[str, str] = {}

    query_sem = asyncio.Semaphore(2)  # 智谱 60/min rate limit；2 路 RAG 查询并发
    QUERY_TIMEOUT_S = 30.0  # 单题最长耗时（含检索 + LLM 生成）

    total = len(items)
    # exact 题型直接走单路混合检索，跳过多路改写（exact 是知识库原问题，改写几乎无收益）
    exact_questions = {item["question"] for item in items if item.get("type") == "exact"}
    logger.info(f"  题型分布: {len(exact_questions)} exact / {total - len(exact_questions)} 其他（exact 跳过多路改写）")

    hybrid_retriever = rag.hybrid_retriever  # exact 路径用

    async def query_one(idx: int, item: dict):
        async with query_sem:
            try:
                if item["question"] in exact_questions:
                    # exact 题：直接单路混合检索，跳过 rewriter 的 LLM 调用
                    loop = asyncio.get_running_loop()
                    sources = await loop.run_in_executor(
                        None,
                        lambda: hybrid_retriever.retrieve(query=item["question"], top_k=rag.settings.rerank_top_k),
                    )
                    if rag.reranker.is_available() and sources:
                        sources = rag.reranker.rerank(
                            query=item["question"], documents=sources,
                            top_k=rag.settings.rerank_top_k,
                        )
                    sources = rag._process_results(sources)
                    context = rag._build_context(sources[: rag.settings.rerank_top_k])
                    messages = rag._build_messages(item["question"], context)
                    answer = await loop.run_in_executor(
                        None, lambda: rag.llm_service.chat(messages)
                    )
                    return item, answer, sources[: rag.settings.rerank_top_k]
                # 其他题型：走完整 rag.query（多路改写 + 混合检索 + 生成）
                result = await asyncio.wait_for(
                    rag.query(item["question"]),
                    timeout=QUERY_TIMEOUT_S,
                )
                rag_answer = result.get("answer", "")
                rag_answer = rag_answer or "(空回答)"
                return item, rag_answer, result.get("sources", [])
            except asyncio.TimeoutError:
                logger.warning(f"题目 {item.get('id', '?')} RAG 超时 (>={QUERY_TIMEOUT_S}s)，跳过")
                raise
            except Exception as e:
                logger.warning(f"题目 {item.get('id', '?')} RAG 失败: {e}")
                raise

    all_query_results = await asyncio.gather(
        *[query_one(idx, item) for idx, item in enumerate(items)],
        return_exceptions=True,
    )

    for idx, (item, result_or_exc) in enumerate(zip(items, all_query_results)):
        if isinstance(result_or_exc, BaseException):
            errors.append(item.get("id", "unknown"))
        else:
            item_obj, rag_answer, sources = result_or_exc
            ragas_data["question"].append(item_obj["question"])
            ragas_data["answer"].append(rag_answer)
            contexts = [
                f"{s.get('question', '')}\n{s.get('answer', '')}"
                for s in sources
            ]
            ragas_data["contexts"].append(contexts)
            ragas_data["ground_truth"].append(item_obj["ground_truth"])
            item_id = item_obj.get("id", item_obj["question"][:8])
            successful_ids.append(item_id)
            answers_map[item_id] = rag_answer
        if progress_callback:
            progress_callback(idx + 1, total)

    if not ragas_data["question"]:
        return EvalSummary(
            results=[EvalResult(id=i, success=False, error="RAG 失败") for i in errors],
            aggregated={},
            errors=errors,
            error_rate=1.0,
        )

    # 检查 checkpoint：复用 phase 1 已成功题目的 RAGAS 评分（按 id 索引）
    checkpoint = _load_ragas_checkpoint()
    if checkpoint:
        ckpt_ids = set(checkpoint.get("successful_ids", []))
        cur_ids = set(successful_ids)
        if ckpt_ids == cur_ids and checkpoint.get("per_item"):
            logger.info(f"  发现有效 RAGAS checkpoint（{len(checkpoint['per_item'])} 条），跳过 phase 2")
            aggregated = checkpoint["aggregated"]
            per_item_metrics = checkpoint["per_item"]
            id_to_metrics = {item_id: per_item_metrics[i] for i, item_id in enumerate(successful_ids)}
            # 构造 results 直接返回
            q_map = {item["id"]: item["question"] for item in items}
            results = [
                EvalResult(id=i, success=True, question=q_map.get(i, ""), answer=answers_map.get(i, ""), metrics=id_to_metrics.get(i, {}))
                for i in successful_ids
            ]
            results += [EvalResult(id=e, success=False) for e in errors]
            return EvalSummary(
                results=results, aggregated=aggregated, errors=errors,
                error_rate=len(errors) / len(items) if items else 0,
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

            aggregated, per_item_metrics = await _evaluate_v04(
                ragas_data, faithfulness_m, answer_relevancy_m,
                context_precision_m, context_recall_m,
                progress_callback=progress_callback,
                phase_offset=len(items),
                phase_total=len(items) * 2,
            )
            # 把逐题指标填回 EvalResult
            id_to_metrics = {item_id: per_item_metrics[i] for i, item_id in enumerate(successful_ids)}
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
    # Build id→question map for filling
    q_map = {item["id"]: item["question"] for item in items}
    results = [EvalResult(id=i, success=True, question=q_map.get(i, ""), answer=answers_map.get(i, ""), metrics=id_to_metrics.get(i, {})) for i in successful_ids]
    results += [EvalResult(id=e, success=False) for e in errors]

    # 保存 checkpoint（下次重启可跳过 phase 2）
    _save_ragas_checkpoint(aggregated, id_to_metrics, successful_ids)

    return EvalSummary(
        results=results,
        aggregated=aggregated,
        errors=errors,
        error_rate=len(errors) / len(items) if items else 0,
    )


def _load_ragas_checkpoint() -> dict | None:
    """加载 RAGAS checkpoint（如果有）"""
    if not RAGAS_CHECKPOINT_PATH.exists():
        return None
    try:
        return json.loads(RAGAS_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"checkpoint 加载失败: {e}")
        return None


def _save_ragas_checkpoint(aggregated: dict, per_item: dict, successful_ids: list[str]):
    """保存 RAGAS checkpoint"""
    try:
        RAGAS_CHECKPOINT_PATH.write_text(
            json.dumps({
                "timestamp": time.strftime("%Y-%m-%dT%H-%M-%S"),
                "successful_ids": successful_ids,
                "aggregated": aggregated,
                "per_item": per_item,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"  RAGAS checkpoint 已保存: {RAGAS_CHECKPOINT_PATH.name}")
    except Exception as e:
        logger.warning(f"checkpoint 保存失败: {e}")


def clear_ragas_checkpoint():
    """手动清理 RAGAS checkpoint（外部调用）"""
    if RAGAS_CHECKPOINT_PATH.exists():
        RAGAS_CHECKPOINT_PATH.unlink()


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
        prompt_variant=settings.query_rewrite_prompt_variant,
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

    # 每个 plan 独立 Semaphore(N)，让 4 个 plan 真正并行跑（之前共享一个 sem 是串行）
    plan_sems = {name: asyncio.Semaphore(1) for name in plans}

    async def run_plan(name: str, plan_fn):
        sem = plan_sems[name]
        plan_results = []
        for item in items:
            async with sem:
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
