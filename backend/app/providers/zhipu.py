"""智谱 API Provider 实现

包装 zhipuai.ZhipuAI SDK，实现 LLMProvider 和 EmbeddingProvider。
"""

import logging
from collections.abc import Generator

from zhipuai import ZhipuAI

from app.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.providers.base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)


class ZhipuLLMProvider(LLMProvider):
    """智谱 LLM 提供者（GLM-4-Flash 等）"""

    def __init__(self):
        settings = get_settings()
        if not settings.zhipu_api_key:
            raise ExternalServiceError("智谱API", "未配置 ZHIPU_API_KEY")

        self.client = ZhipuAI(
            api_key=settings.zhipu_api_key,
            timeout=settings.llm_timeout_s,
        )
        self.model = settings.llm_model
        self.default_temperature = settings.llm_temperature
        self.default_max_tokens = settings.llm_max_tokens
        logger.info(f"智谱 LLM Provider 已初始化，模型: {self.model}")

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.default_max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"智谱 LLM 调用失败: {e}")
            raise ExternalServiceError("智谱API", str(e))

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Generator[str, None, None]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.default_max_tokens,
                stream=True,
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"智谱 LLM 流式调用失败: {e}")
            raise ExternalServiceError("智谱API", str(e))

    def check_health(self) -> str:
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return "ok"
        except Exception as e:
            logger.warning(f"智谱 LLM 健康检查失败: {e}")
            return "error"


class ZhipuEmbeddingProvider(EmbeddingProvider):
    """智谱 Embedding 提供者（embedding-3 等）"""

    def __init__(self):
        settings = get_settings()
        if not settings.zhipu_api_key:
            raise ExternalServiceError("智谱API", "未配置 ZHIPU_API_KEY")

        self.client = ZhipuAI(
            api_key=settings.zhipu_api_key,
            timeout=settings.llm_timeout_s,
        )
        self.model = settings.embedding_model
        logger.info(f"智谱 Embedding Provider 已初始化，模型: {self.model}")

    def embed_query(self, text: str) -> list[float]:
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"智谱 Embedding 调用失败: {e}")
            raise ExternalServiceError("智谱Embedding", str(e))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"智谱批量 Embedding 调用失败: {e}")
            raise ExternalServiceError("智谱Embedding", str(e))