"""LLM / Embedding Provider 包

提供统一的接口定义、工厂函数和内置实现。
使用方式：

    from app.providers import create_llm_provider, LLMProvider

    provider = create_llm_provider()      # 从 config 自动选择
    result = provider.chat([...])
"""

from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.factory import create_embedding_provider, create_llm_provider
from app.providers.openai_style import (
    OpenAIStyleEmbeddingProvider,
    OpenAIStyleLLMProvider,
)
from app.providers.zhipu import ZhipuEmbeddingProvider, ZhipuLLMProvider

__all__ = [
    "LLMProvider",
    "EmbeddingProvider",
    "ZhipuLLMProvider",
    "ZhipuEmbeddingProvider",
    "OpenAIStyleLLMProvider",
    "OpenAIStyleEmbeddingProvider",
    "create_llm_provider",
    "create_embedding_provider",
]