"""LLM / Embedding Provider 抽象接口

所有 LLM 和 Embedding 提供者必须实现本模块定义的抽象基类。
"""

from abc import ABC, abstractmethod
from collections.abc import Generator


class LLMProvider(ABC):
    """LLM 提供者抽象

    同步接口——下游调用方（RAGService / QueryRewriter）通过线程池包裹，
    Provider 自身不需要处理 asyncio。

    实现者需实现：
    - chat(): 同步对话（成功后设置 _last_usage）
    - chat_stream(): 同步流式生成（yield token）
    - check_health(): 连通性检查
    """

    def __init__(self):
        self._last_usage: dict | None = None

    @property
    def last_usage(self) -> dict | None:
        """最近一次 chat() 调用返回的 token 用量。

        格式: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        仅在 chat() 成功后可用；chat_stream() 通常不返回 usage。
        """
        return self._last_usage

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """同步对话

        Args:
            messages: OpenAI 格式消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度（覆盖默认）
            max_tokens: 最大输出 token（覆盖默认）

        Returns:
            模型生成的文本
        """

    @abstractmethod
    def chat_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Generator[str, None, None]:
        """同步流式生成

        返回 Python 生成器，逐个 yield token。
        由外层 LLMService 的 chat_stream 包装为 async generator。

        Args:
            同上

        Yields:
            逐 token 文本片段
        """

    @abstractmethod
    def check_health(self) -> str:
        """健康检查

        发起一次极轻量的 LLM 调用确认服务连通性。

        Returns:
            "ok" 或 "error"
        """


class EmbeddingProvider(ABC):
    """Embedding 提供者抽象

    同步接口——下游调用方均在线程池中调用。
    """

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """将单条文本转为向量

        Args:
            text: 输入文本

        Returns:
            浮点数向量
        """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转为向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """