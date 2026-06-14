"""Embedding 服务封装（Facade）

委托给 EmbeddingProvider 实际执行，保持向后兼容的导入路径。
"""

from app.providers import EmbeddingProvider, create_embedding_provider


class EmbedService:
    """Embedding 服务

    轻量 facade 委托给 EmbeddingProvider。
    可直接构造，也可注入自定义 Provider：

        service = EmbedService()
        service = EmbedService(provider=MyEmbeddingProvider())
    """

    def __init__(self, provider: EmbeddingProvider | None = None):
        self._provider = provider or create_embedding_provider()

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    def embed_query(self, text: str) -> list[float]:
        return self._provider.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._provider.embed_documents(texts)