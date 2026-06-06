"""RAG 核心服务

负责将检索、Re-ranking、查询改写、LLM 生成串联起来。
"""

import logging
from collections.abc import AsyncGenerator

from app.config import get_settings
from app.core.vectorstore import VectorStore
from app.retrievers.hybrid_retriever import HybridRetriever
from app.rerankers.bge_reranker import BGEReranker
from app.services.llm_service import LLMService
from app.services.embed_service import EmbedService

logger = logging.getLogger(__name__)

# 系统提示
SYSTEM_PROMPT = """你是一个专业的面试助手。你的任务是根据提供的参考资料回答用户的面试问题。

规则：
1. 只根据提供的参考资料回答问题，不要编造信息
2. 如果参考资料中没有相关内容，明确告知用户"根据现有知识库，我暂时无法回答这个问题"
3. 回答要准确、简洁、有条理，使用 Markdown 格式
4. 不要在回答中添加来源引用，系统会自动处理
"""

# 查询改写提示
REWRITE_PROMPT = """你是一个搜索查询优化器。用户的问题可能比较口语化或模糊。
请将其改写为更适合检索的精确查询，保持原意但更具体。
只输出改写后的查询，不要解释。

用户问题：{question}
改写后的查询："""


class RAGService:
    """RAG 核心服务"""

    def __init__(self):
        self.settings = get_settings()
        self.vector_store = VectorStore()
        self.hybrid_retriever = HybridRetriever(self.vector_store)
        self.reranker = BGEReranker()
        self.llm_service = LLMService()
        self.embed_service = EmbedService()

    async def query(
        self,
        question: str,
        chat_history: list[dict] | None = None,
    ) -> dict:
        """问答（普通返回）"""
        import asyncio
        loop = asyncio.get_event_loop()

        # 直接使用原始问题
        rewritten = question

        # 2-3. 混合检索 + Re-ranking（在线程池中运行）
        def _retrieve_and_rerank():
            retrieved = self.hybrid_retriever.retrieve(
                query=rewritten,
                top_k=self.settings.retrieval_top_k,
            )
            sources = self._process_results(retrieved)
            if self.reranker.is_available() and sources:
                sources = self.reranker.rerank(
                    query=rewritten,
                    documents=sources,
                    top_k=self.settings.rerank_top_k,
                )
            return sources

        sources = await loop.run_in_executor(None, _retrieve_and_rerank)

        # 4. 构建上下文
        context = self._build_context(sources[: self.settings.rerank_top_k])

        # 5. 构建消息
        messages = self._build_messages(question, context, chat_history)

        # 6. LLM 生成（在线程池中运行避免阻塞事件循环）
        import asyncio
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(
            None, lambda: self.llm_service.chat(messages)
        )

        return {
            "answer": answer,
            "sources": sources[: self.settings.rerank_top_k],
        }

    async def query_stream(
        self,
        question: str,
        chat_history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """问答（流式返回，同时检索前置）"""
        import asyncio

        # 直接使用原始问题，跳过查询改写（改写需要额外 LLM 调用，太慢）
        rewritten = question

        # 2-3. 混合检索 + Re-ranking（同步操作，在线程池中运行）
        loop = asyncio.get_event_loop()

        def _retrieve_and_rerank():
            retrieved = self.hybrid_retriever.retrieve(
                query=rewritten,
                top_k=self.settings.retrieval_top_k,
            )
            sources = self._process_results(retrieved)
            if self.reranker.is_available() and sources:
                sources = self.reranker.rerank(
                    query=rewritten,
                    documents=sources,
                    top_k=self.settings.rerank_top_k,
                )
            return sources

        sources = await loop.run_in_executor(None, _retrieve_and_rerank)
        self._last_sources = sources[: self.settings.rerank_top_k]

        # 4. 构建上下文
        context = self._build_context(self._last_sources)

        # 5. 构建消息
        messages = self._build_messages(question, context, chat_history)

        # 6. 流式生成
        async for chunk in self.llm_service.chat_stream(messages):
            yield chunk

    async def _rewrite_query(self, question: str) -> str:
        """用 LLM 改写查询（在线程池中运行避免阻塞事件循环）"""
        import asyncio
        try:
            prompt = REWRITE_PROMPT.format(question=question)
            messages = [{"role": "user", "content": prompt}]
            loop = asyncio.get_event_loop()
            rewritten = await loop.run_in_executor(
                None, lambda: self.llm_service.chat(messages, temperature=0.3, max_tokens=200)
            )
            return rewritten.strip() or question
        except Exception as e:
            logger.warning(f"查询改写失败，使用原始查询: {e}")
            return question

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
            score = doc.get("rerank_score") or doc.get("rrf_score") or 0.0

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
                messages.append(msg)

        # 添加当前问题和上下文
        user_content = f"参考资料：\n{context}\n\n用户问题：{question}"
        messages.append({"role": "user", "content": user_content})

        return messages
