"""多路召回合并检索器

对 N 个查询变体并发跑 HybridRetriever，按 chunk 级 id 去重，
score 取 max，累加 matched_queries 便于回溯。
"""

import asyncio
import logging

from app.retrievers.hybrid_retriever import HybridRetriever
from app.retrievers.query_rewriter import QueryRewriter

logger = logging.getLogger(__name__)


class MultiQueryRetriever:
    """多路改写 + 并发检索 + 去重合并。

    入口：
    - `retrieve_with_queries(queries, top_k)`：直接吃查询列表（测试与 strategy E 用）
    - `retrieve(query, top_k)`：内部调 QueryRewriter 后转发（主链路用）

    返回的 doc 形如 HybridRetriever 输出，附加 `matched_queries` 字段。
    """

    def __init__(
        self,
        hybrid: HybridRetriever,
        n: int = 3,
        top_k: int = 20,
        rewriter: QueryRewriter | None = None,
    ):
        self.hybrid = hybrid
        self.n = n
        self.top_k = top_k
        self.rewriter = rewriter

    def set_rewriter(self, rewriter: QueryRewriter) -> None:
        """延迟注入 rewriter（rag_service 构造时 rewriter 还没建好时用）。"""
        self.rewriter = rewriter

    def retrieve_with_queries(
        self,
        queries: list[str],
        top_k: int | None = None,
    ) -> list[dict]:
        """同步入口：对 queries 并发跑 hybrid.retrieve，合并去重。

        自动适配 async 上下文：已有 running loop 时在线程中跑独立事件循环，
        避免 asyncio.new_event_loop() 在 async 上下文中崩溃（Python 3.10+）。
        """
        coro = self.aretrieve_with_queries(queries, top_k)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # 没有 running loop → 直接 run（原行为）
            return asyncio.run(coro)
        else:
            # 已有 running loop → 在线程中跑独立 event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()

    async def aretrieve_with_queries(
        self,
        queries: list[str],
        top_k: int | None = None,
    ) -> list[dict]:
        """异步入口：asyncio.gather 并发 N 路 hybrid.retrieve，去重合并。"""
        if not queries:
            return []
        k = top_k or self.top_k
        # 每路取 2x top_k 留合并余量
        per_query_k = max(k * 2, 10)

        loop = asyncio.get_running_loop()

        def _one(q: str) -> list[dict]:
            try:
                return self.hybrid.retrieve(query=q, top_k=per_query_k)
            except Exception as e:
                logger.warning(f"MultiQuery: 单路失败 query='{q[:30]}...': {e}")
                return []

        # 并发跑 N 路（线程池）
        tasks = [loop.run_in_executor(None, _one, q) for q in queries]
        results_per_query: list[list[dict]] = await asyncio.gather(*tasks)

        # 合并去重
        merged = self._merge(results_per_query, queries=queries)
        return merged[:k]

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        """同步主入口：先改写再检索。需要注入 rewriter。"""
        if self.rewriter is None:
            raise RuntimeError("rewriter 未注入，调用 set_rewriter()")
        queries = self.rewriter.rewrite(query)
        return self.retrieve_with_queries(queries, top_k=top_k)

    async def aretrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        """异步主入口：先改写再检索。供 rag_service 的 async 链路使用。"""
        if self.rewriter is None:
            raise RuntimeError("rewriter 未注入，调用 set_rewriter()")
        queries = await self.rewriter.arewrite(query)
        return await self.aretrieve_with_queries(queries, top_k=top_k)

    @staticmethod
    def _merge(
        results_per_query: list[list[dict]],
        queries: list[str],
    ) -> list[dict]:
        """按 chunk 级 doc['id'] 去重，score 取 max，累加 matched_queries。"""
        merged: dict[str, dict] = {}
        for q_idx, docs in enumerate(results_per_query):
            q = queries[q_idx] if q_idx < len(queries) else ""
            for doc in docs:
                doc_id = doc.get("id")
                if not doc_id:
                    continue
                # 兼容 rrf_score / rerank_score
                score = doc.get("rerank_score") or doc.get("rrf_score") or 0.0
                if doc_id in merged:
                    existing = merged[doc_id]
                    if score > existing.get("rrf_score", 0.0):
                        existing["rrf_score"] = score
                        # 更新 text/metadata 以分数更高的为准
                        for key in ("text", "metadata", "distance", "bm25_score"):
                            if key in doc:
                                existing[key] = doc[key]
                    matched = existing.setdefault("matched_queries", [])
                    if q not in matched:
                        matched.append(q)
                else:
                    new_doc = dict(doc)
                    new_doc.setdefault("matched_queries", [q])
                    merged[doc_id] = new_doc

        # 按 rrf_score 降序
        return sorted(
            merged.values(),
            key=lambda d: d.get("rrf_score", 0.0),
            reverse=True,
        )
