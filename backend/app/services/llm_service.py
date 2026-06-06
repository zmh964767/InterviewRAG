"""智谱 LLM 服务封装"""

import logging
from collections.abc import AsyncGenerator

from zhipuai import ZhipuAI

from app.config import get_settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class LLMService:
    """智谱大模型服务"""

    def __init__(self):
        settings = get_settings()
        if not settings.zhipu_api_key:
            raise ExternalServiceError("智谱API", "未配置 ZHIPU_API_KEY")

        self.client = ZhipuAI(api_key=settings.zhipu_api_key)
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        logger.info(f"智谱 LLM 已初始化，模型: {self.model}")

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """普通对话"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"智谱 API 调用失败: {e}")
            raise ExternalServiceError("智谱API", str(e))

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话（真正的逐 token 流式）"""
        import asyncio
        import queue

        try:
            loop = asyncio.get_event_loop()
            q: queue.Queue = queue.Queue()
            sentinel = object()  # 结束标记

            def _sync_stream():
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature or self.temperature,
                        max_tokens=max_tokens or self.max_tokens,
                        stream=True,
                    )
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            q.put(chunk.choices[0].delta.content)
                except Exception as e:
                    q.put(e)
                finally:
                    q.put(sentinel)

            # 在线程池中启动同步流
            loop.run_in_executor(None, _sync_stream)

            # 逐个 yield chunk
            while True:
                chunk = await loop.run_in_executor(None, q.get)
                if chunk is sentinel:
                    break
                if isinstance(chunk, Exception):
                    raise chunk
                yield chunk
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"智谱 API 流式调用失败: {e}")
            raise ExternalServiceError("智谱API", str(e))

    def check_health(self) -> str:
        """检查 LLM 连接状态"""
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return "ok"
        except Exception as e:
            logger.warning(f"LLM 健康检查失败: {e}")
            return "error"
