"""LLM 服务封装（Facade）

委托给 LLMProvider 实际执行，保持向后兼容的导入路径。
"""

import asyncio
import logging
import queue
import threading
from collections.abc import AsyncGenerator

from app.providers import LLMProvider, create_llm_provider

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务

    轻量 facade，负责：
    1. 将 Provider 的同步 stream（Generator）包装为 async generator
    2. 保持现有调用方（RAGService / QueryRewriter）的导入和接口不变

    可直接构造（使用默认 Provider），也可注入自定义 Provider：

        service = LLMService()
        service = LLMService(provider=MyCustomProvider())
    """

    def __init__(self, provider: LLMProvider | None = None):
        self._provider = provider or create_llm_provider()

    # -- 委托方法 -----------------------------------------------------------

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """同步对话（委托给 Provider）"""
        return self._provider.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话（sync generator → async generator 适配）

        使用 threading.Event 取消信号：当消费方提前停止迭代时，
        通过 cancelled.set() 通知后台线程停止，并在 finally 中
        等待线程退出（最多 5 秒），避免线程泄漏。
        """
        loop = asyncio.get_running_loop()
        q: queue.Queue = queue.Queue()
        sentinel = object()
        cancelled = threading.Event()

        def _sync_stream():
            """在线程中消费 Provider 的 sync stream"""
            try:
                for token in self._provider.chat_stream(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    if cancelled.is_set():
                        break
                    q.put(token)
            except Exception as e:
                if not cancelled.is_set():
                    q.put(e)
            finally:
                q.put(sentinel)

        fut = loop.run_in_executor(None, _sync_stream)

        try:
            while True:
                chunk = await loop.run_in_executor(None, q.get)
                if chunk is sentinel:
                    break
                if isinstance(chunk, Exception):
                    raise chunk
                yield chunk
        finally:
            cancelled.set()
            try:
                await asyncio.wait_for(asyncio.wrap_future(fut), timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                pass

    def check_health(self) -> str:
        """健康检查（委托给 Provider）"""
        return self._provider.check_health()