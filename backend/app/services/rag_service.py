"""RAG 核心服务

负责将检索、Re-ranking、查询改写、LLM 生成串联起来。
"""

import asyncio
from collections.abc import AsyncGenerator

import structlog

from app.cache.sqlite_cache import SQLiteCacheBackend
from app.config import get_settings
from app.core.metrics import CACHE_HITS, CACHE_MISSES, track_stage
from app.core.vectorstore import VectorStore
from app.providers import create_embedding_provider
from app.retrievers.hybrid_retriever import HybridRetriever
from app.retrievers.multi_query_retriever import MultiQueryRetriever
from app.retrievers.query_rewriter import QueryRewriter
from app.retrievers.small_to_big import SmallToBigRetriever
from app.rerankers.bge_reranker import BGEReranker
from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)


class _StreamWithSources:
    """包装 async generator + 附加 sources 属性供调用方读取。

    `__aiter__` 返回底层 chat_stream async iterator（不是 async 方法），
    这是修复 stream=true 报 "got coroutine" 错误的关键。
    """

    def __init__(self, sources: list[dict], inner: AsyncGenerator[str, None]):
        self.sources = sources
        self._inner = inner

    def __aiter__(self) -> AsyncGenerator[str, None]:
        return self._inner

# 系统提示
SYSTEM_PROMPT = """你是一个专业的面试助手。你的任务是根据提供的参考资料回答用户的面试问题。

规则：
1. 只根据提供的参考资料回答问题，不要编造信息
2. 如果参考资料中没有相关内容，明确告知用户"根据现有知识库，我暂时无法回答这个问题"
3. 回答要准确、简洁、有条理，使用 Markdown 格式
4. 不要在回答中添加来源引用，系统会自动处理
"""

class RAGService:
    """RAG 核心服务"""

    def __init__(self):
        self.settings = get_settings()
        self.vector_store = VectorStore()
        self.hybrid_retriever = HybridRetriever(self.vector_store)
        self.s2b_retriever = SmallToBigRetriever(self.vector_store)
        self.reranker = BGEReranker()
        self.llm_service = LLMService()

        # 语义缓存
        self.cache = SQLiteCacheBackend() if self.settings.cache_enabled else None
        self.embed_provider = create_embedding_provider()

        # 多路改写：rewriter 永远建（让 multi 拿到），multi_query_enabled 是 kill switch
        self.rewriter = QueryRewriter(
            self.llm_service,
            n=self.settings.multi_query_n,
            timeout_s=self.settings.multi_query_timeout_s,
            prompt_variant=self.settings.query_rewrite_prompt_variant,
        )
        self.multi_query_retriever = MultiQueryRetriever(
            self.hybrid_retriever,
            n=self.settings.multi_query_n,
            top_k=self.settings.retrieval_top_k,
        )
        self.multi_query_retriever.set_rewriter(self.rewriter)

    async def _retrieve(self, question: str) -> list[dict]:
        """统一检索入口：small_to_big / multi_query / 单路混合检索。

        返回的是处理后的 sources（dict 形态，含 id/question/answer/score）。
        在 async 上下文里直接 await，避免嵌套 event loop。
        """
        if self.settings.small_to_big_enabled:
            async with track_stage("retrieval"):
                loop = asyncio.get_running_loop()
                raw = await loop.run_in_executor(
                    None,
                    lambda: self.s2b_retriever.retrieve(
                        query=question, top_k=self.settings.retrieval_top_k,
                    ),
                )
        elif self.settings.multi_query_enabled:
            async with track_stage("retrieval"):
                raw = await self.multi_query_retriever.aretrieve(
                    query=question, top_k=self.settings.retrieval_top_k
                )
        else:
            async with track_stage("retrieval"):
                # 单路走线程池（hybrid.retrieve 是同步阻塞）
                loop = asyncio.get_running_loop()
                raw = await loop.run_in_executor(
                    None,
                    lambda: self.hybrid_retriever.retrieve(
                        query=question, top_k=self.settings.retrieval_top_k
                    ),
                )
        if self.reranker.is_available() and raw:
            async with track_stage("rerank"):
                loop = asyncio.get_running_loop()
                raw = await loop.run_in_executor(
                    None,
                    lambda: self.reranker.rerank(
                        query=question,
                        documents=raw,
                        top_k=self.settings.rerank_top_k,
                    ),
                )
        return self._process_results(raw)

    async def _cache_check(self, question: str) -> tuple[dict | None, list[float] | None]:
        """语义缓存查询。

        Returns:
            (cached_result, embedding): 命中时 cached_result 非空；
            未命中时 (None, embedding) — embedding 可供 _cache_put 复用，避免重复计算。
            异常时返回 (None, None)。
        """
        if not self.cache:
            return None, None
        try:
            async with track_stage("cache_check"):
                loop = asyncio.get_running_loop()
                embedding = await loop.run_in_executor(
                    None, lambda: self.embed_provider.embed_query(question)
                )
                cached = await loop.run_in_executor(
                    None,
                    lambda: self.cache.get(
                        embedding, self.settings.cache_similarity_threshold
                    ),
                )
                if cached:
                    CACHE_HITS.inc()
                    return cached, embedding
                CACHE_MISSES.inc()
                return None, embedding
        except Exception as e:
            logger.warning("cache_query_error", error=str(e), fallback=True)
            return None, None

    async def _cache_put(self, question: str, result: dict, embedding: list[float] | None = None) -> None:
        """写入缓存（best-effort，失败不影响返回）

        Args:
            question: 查询文本
            result: RAG 结果
            embedding: 预计算的 embedding（可选，为 None 时重新计算）
        """
        if not self.cache:
            return
        try:
            loop = asyncio.get_running_loop()
            if embedding is None:
                embedding = await loop.run_in_executor(
                    None, lambda: self.embed_provider.embed_query(question)
                )
            await loop.run_in_executor(
                None,
                lambda: self.cache.put(
                    question, embedding, result, self.settings.cache_ttl_hours
                ),
            )
        except Exception as e:
            logger.warning("cache_write_error", error=str(e))

    async def query(
        self,
        question: str,
        chat_history: list[dict] | None = None,
    ) -> dict:
        """问答（普通返回）"""
        # 语义缓存查询
        cached, cached_embedding = await self._cache_check(question)
        if cached:
            return cached

        # 检索（多路改写 → 合并 → re-rank）
        sources = await self._retrieve(question)

        # 构建上下文
        context = self._build_context(sources[: self.settings.rerank_top_k])

        # 构建消息
        messages = self._build_messages(question, context, chat_history)

        # LLM 生成（在线程池中运行避免阻塞事件循环）
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(
            None, lambda: self.llm_service.chat(messages)
        )

        result = {
            "answer": answer,
            "sources": sources[: self.settings.rerank_top_k],
        }

        # 写入缓存（复用 _cache_check 算出的 embedding）
        await self._cache_put(question, result, embedding=cached_embedding)

        return result

    async def query_stream(
        self,
        question: str,
        chat_history: list[dict] | None = None,
    ) -> "_StreamWithSources":
        """问答（流式返回，检索前置）

        本方法是 coroutine（不是 async generator）：
        - 调用方 `gen = await query_stream(...)` 拿到 `_StreamWithSources` 对象
        - `async for chunk in gen` 消费 LLM 流
        - `gen.sources` 读取来源引用（无实例属性竞争：sources 挂在 gen 上，
          不同请求各持自己的 gen，互不干扰）
        """
        # 语义缓存查询：命中时一次性返回完整答案
        cached, cached_embedding = await self._cache_check(question)
        if cached:
            cached_answer = cached["answer"]
            cached_sources = cached.get("sources", [])

            async def _cached_inner() -> AsyncGenerator[str, None]:
                yield cached_answer

            return _StreamWithSources(cached_sources, _cached_inner())

        sources = await self._retrieve(question)
        top_sources = sources[: self.settings.rerank_top_k]

        context = self._build_context(top_sources)
        messages = self._build_messages(question, context, chat_history)

        # 内部 async generator：转发 LLM 流（_StreamWithSources.__aiter__ 直接返回它）
        async def _inner() -> AsyncGenerator[str, None]:
            full_answer = ""
            async for chunk in self.llm_service.chat_stream(messages):
                full_answer += chunk
                yield chunk
            # 流式完成后写入缓存（复用 _cache_check 算出的 embedding）
            await self._cache_put(question, {"answer": full_answer, "sources": top_sources}, embedding=cached_embedding)

        return _StreamWithSources(top_sources, _inner())

    def _process_results(self, raw_results: list[dict]) -> list[dict]:
        """处理检索结果（来自 HybridRetriever）"""
        sources = []
        if not raw_results:
            return sources

        for doc in raw_results:
            # 从文档中提取题目和答案
            doc_text = doc.get("text", "")
            parts = doc_text.split("\n\n答案：", 1)
            question_text = parts[0].replace("题目：", "").strip() if parts else doc_text
            answer_text = parts[1].strip() if len(parts) > 1 else ""

            # 优先使用 rerank_score，其次 rrf_score，最后 0
            score = doc.get("rerank_score")
            if score is None:
                score = doc.get("rrf_score", 0.0)

            sources.append({
                "id": doc.get("id", ""),
                "question": question_text,
                "answer": answer_text,
                "category": doc.get("metadata", {}).get("category", ""),
                "difficulty": doc.get("metadata", {}).get("difficulty", ""),
                "score": round(float(score), 4),
            })

        # 按分数排序
        sources.sort(key=lambda x: x["score"], reverse=True)
        return sources

    def _build_context(self, sources: list[dict]) -> str:
        """构建上下文文本"""
        if not sources:
            return "暂无相关参考资料。"

        context_parts = []
        for i, s in enumerate(sources, 1):
            context_parts.append(
                f"参考资料 {i}（ID: {s['id']}，分类: {s['category']}，相关度: {s['score']}）：\n"
                f"题目：{s['question']}\n"
                f"答案：{s['answer']}"
            )

        return "\n\n---\n\n".join(context_parts)

    def _build_messages(
        self,
        question: str,
        context: str,
        chat_history: list[dict] | None = None,
    ) -> list[dict]:
        """构建 LLM 消息列表"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 添加对话历史
        if chat_history:
            for msg in chat_history[-self.settings.memory_window * 2 :]:
                if msg.get("role") in ("user", "assistant") and msg.get("content"):
                    messages.append(msg)

        # 添加当前问题和上下文
        user_content = f"参考资料：\n{context}\n\n用户问题：{question}"
        messages.append({"role": "user", "content": user_content})

        return messages
