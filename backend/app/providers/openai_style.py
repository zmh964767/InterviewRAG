"""OpenAI 兼容 API Provider 实现

适用于 OpenAI / Azure OpenAI / Ollama / 任意 OpenAI 兼容端点。
"""

import re
from collections.abc import Generator

import structlog
from openai import OpenAI

from app.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.providers.base import EmbeddingProvider, LLMProvider

logger = structlog.get_logger(__name__)


def _sanitize_error(exc: Exception) -> str:
    """Remove potential API keys from error messages."""
    msg = str(exc)
    msg = re.sub(r'(?:sk-|key[=:]\s*)[A-Za-z0-9_-]{20,}', '[REDACTED]', msg)
    return msg


class OpenAIStyleLLMProvider(LLMProvider):
    """OpenAI 兼容 LLM 提供者（GPT / Ollama / 任意兼容端点）"""

    def __init__(self):
        super().__init__()
        settings = get_settings()
        api_key = settings.openai_api_key
        if not api_key:
            raise ExternalServiceError(
                "OpenAI兼容API", "未配置 OPENAI_API_KEY（llm_provider=openai 时必填）"
            )

        base_url = settings.openai_base_url or None  # 空字串 → None（即 OpenAI 官方默认）
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=settings.llm_timeout_s,
        )
        # model 优先使用 openai 专用配置，其次公共 llm_model
        self.model = settings.openai_llm_model or settings.llm_model
        self.default_temperature = settings.llm_temperature
        self.default_max_tokens = settings.llm_max_tokens
        logger.info(
            "provider_init",
            provider="openai",
            model=self.model,
            endpoint=base_url or "default",
        )

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
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
            )
            # 记录 token 用量（供 LLMService 读取并上报指标）
            if hasattr(response, "usage") and response.usage:
                self._last_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            else:
                self._last_usage = None
            return response.choices[0].message.content or ""
        except Exception as e:
            self._last_usage = None
            logger.error("llm_call_failed", provider="openai", error=_sanitize_error(e))
            raise ExternalServiceError("OpenAI兼容API", _sanitize_error(e))

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
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
                stream=True,
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("llm_stream_failed", provider="openai", error=_sanitize_error(e))
            raise ExternalServiceError("OpenAI兼容API", _sanitize_error(e))

    def check_health(self) -> str:
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return "ok"
        except Exception as e:
            logger.warning("health_check_failed", provider="openai", error=str(e))
            return "error"


class OpenAIStyleEmbeddingProvider(EmbeddingProvider):
    """OpenAI 兼容 Embedding 提供者（text-embedding-3-small 等）"""

    def __init__(self):
        settings = get_settings()
        api_key = settings.openai_api_key
        if not api_key:
            raise ExternalServiceError(
                "OpenAI兼容API", "未配置 OPENAI_API_KEY（embedding_provider=openai 时必填）"
            )

        base_url = settings.openai_base_url or None
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=settings.llm_timeout_s,
        )
        self.model = settings.openai_embedding_model or settings.embedding_model
        logger.info(
            "embedding_provider_init",
            provider="openai",
            model=self.model,
            endpoint=base_url or "default",
        )

    def embed_query(self, text: str) -> list[float]:
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("embedding_call_failed", provider="openai", error=_sanitize_error(e))
            raise ExternalServiceError("OpenAI兼容API", _sanitize_error(e))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error("embedding_batch_failed", provider="openai", error=_sanitize_error(e))
            raise ExternalServiceError("OpenAI兼容API", _sanitize_error(e))