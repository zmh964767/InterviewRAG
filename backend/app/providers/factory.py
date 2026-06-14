"""Provider 工厂

根据配置的 provider type 创建对应的 LLM / Embedding 实例。
"""

import logging

from app.config import get_settings
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.openai_style import (
    OpenAIStyleEmbeddingProvider,
    OpenAIStyleLLMProvider,
)
from app.providers.zhipu import ZhipuEmbeddingProvider, ZhipuLLMProvider

logger = logging.getLogger(__name__)

# provider type → (LLM 实现类, Embedding 实现类)
_PROVIDER_MAP: dict[str, tuple[type[LLMProvider], type[EmbeddingProvider]]] = {
    "zhipu": (ZhipuLLMProvider, ZhipuEmbeddingProvider),
    "openai": (OpenAIStyleLLMProvider, OpenAIStyleEmbeddingProvider),
}


def _resolve_provider(ptype: str) -> tuple[type[LLMProvider], type[EmbeddingProvider]]:
    """解析 provider type，未知 type 抛出包含可选值的错误。"""
    if ptype not in _PROVIDER_MAP:
        valid = ", ".join(sorted(_PROVIDER_MAP))
        raise ValueError(f"未知 provider type '{ptype}'，可选: {valid}")
    return _PROVIDER_MAP[ptype]


def create_llm_provider(provider_type: str | None = None) -> LLMProvider:
    """创建 LLM Provider

    Args:
        provider_type: provider type，默认从 config.llm_provider 读取

    Returns:
        LLMProvider 实例
    """
    settings = get_settings()
    ptype = provider_type or settings.llm_provider
    cls, _ = _resolve_provider(ptype)
    logger.info(f"创建 LLM Provider: {ptype}")
    return cls()


def create_embedding_provider(provider_type: str | None = None) -> EmbeddingProvider:
    """创建 Embedding Provider

    Args:
        provider_type: provider type，默认从 config.embedding_provider 读取

    Returns:
        EmbeddingProvider 实例
    """
    settings = get_settings()
    ptype = provider_type or settings.embedding_provider
    _, cls = _resolve_provider(ptype)
    logger.info(f"创建 Embedding Provider: {ptype}")
    return cls()