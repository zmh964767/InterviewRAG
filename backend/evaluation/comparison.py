"""对比实验

对比五种检索策略的效果：
- 方案 A：纯向量检索（baseline）
- 方案 B：混合检索（向量 + BM25）
- 方案 C：混合检索 + Re-ranking
- 方案 D：小块检索 + 大块生成
- 方案 E：多路 Query 改写 + 混合检索
"""

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def run_comparison():
    """运行对比实验"""

    # 1. 加载评估数据集
    eval_path = Path(__file__).parent / "eval_dataset.json"
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    eval_items = [item for item in eval_data if item["type"] != "irrelevant"]

    # 2. 初始化组件
    from app.config import get_settings
    from app.core.vectorstore import VectorStore
    from app.retrievers.hybrid_retriever import HybridRetriever
    from app.retrievers.multi_query_retriever import MultiQueryRetriever
    from app.retrievers.query_rewriter import QueryRewriter
    from app.retrievers.small_to_big import SmallToBigRetriever
    from app.rerankers.bge_reranker import BGEReranker
    from app.services.llm_service import LLMService

    settings = get_settings()
    vector_store = VectorStore()
    hybrid_retriever = HybridRetriever(vector_store)
    s2b_retriever = SmallToBigRetriever(vector_store)
    reranker = BGEReranker()
    llm_service = LLMService()

    # 方案 E：多路改写 + 混合检索（共享 rewriter 与 multi retriever）
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

    # 3. 定义四种方案
    async def plan_a(question: str) -> dict:
        """方案 A：纯向量检索（baseline）"""
        results = vector_store.query(query_text=question, n_results=5)
        sources = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                sources.append({"text": doc, "score": 1 - results["distances"][0][i]})
        return {"sources": sources}

    async def plan_b(question: str) -> dict:
        """方案 B：混合检索（向量 + BM25）"""
        results = hybrid_retriever.retrieve(query=question, top_k=5)
        return {"sources": results}

    async def plan_c(question: str) -> dict:
        """方案 C：混合检索 + Re-ranking"""
        results = hybrid_retriever.retrieve(query=question, top_k=20)
        if reranker.is_available():
            results = reranker.rerank(query=question, documents=results, top_k=5)
        return {"sources": results[:5]}

    async def plan_d(question: str) -> dict:
        """方案 D：小块检索 + 大块生成"""
        results = s2b_retriever.retrieve(query=question, top_k=5, n_candidates=20)
        return {"sources": results}

    async def plan_e(question: str) -> dict:
        """方案 E：多路 Query 改写 + 混合检索（去重合并）"""
        # 改写：单次 LLM 调用，5s 超时回退
        queries = rewriter.rewrite(question)
        # 多路并发检索 + 去重合并
        results = multi_query_retriever.retrieve_with_queries(queries, top_k=5)
        return {"sources": results}

    plans = {
        "A_纯向量": plan_a,
        "B_混合检索": plan_b,
        "C_混合+Rerank": plan_c,
        "D_小块检索大块生成": plan_d,
        "E_多路改写混合": plan_e,
    }

    # 4. 运行对比
    results = {}

    for plan_name, plan_func in plans.items():
        logger.info(f"运行方案: {plan_name}")
        correct = 0
        total = len(eval_items)

        for item in eval_items:
            question = item["question"]
            try:
                result = await plan_func(question)
                sources = result.get("sources", [])

                # 简单判断：检索结果中是否包含相关内容
                if sources:
                    top_text = sources[0].get("text", "") if isinstance(sources[0], dict) else str(sources[0])
                    ground_truth = item["ground_truth"]
                    # 关键词重叠检测
                    overlap = sum(1 for word in ground_truth[:50] if word in top_text)
                    if overlap > 5:
                        correct += 1
            except Exception as e:
                logger.error(f"方案 {plan_name} 查询失败: {e}")

        accuracy = correct / total if total > 0 else 0
        results[plan_name] = {
            "correct": correct,
            "total": total,
            "accuracy": round(accuracy, 4),
        }

    # 5. 输出对比报告
    print("\n" + "=" * 70)
    print("检索策略对比实验")
    print("=" * 70)
    print(f"{'方案':<25} {'正确':>8} {'总数':>8} {'准确率':>10}")
    print("-" * 70)
    for plan_name, result in results.items():
        print(
            f"{plan_name:<25} {result['correct']:>8} {result['total']:>8} {result['accuracy']:>10.2%}"
        )
    print("=" * 70)

    # 保存结果
    output_path = Path(__file__).parent / "comparison_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"对比结果已保存到 {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_comparison())
