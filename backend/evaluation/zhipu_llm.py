"""智谱 LLM 适配层

兼容 ragas 0.2.x 和 0.4+：
- ragas 0.4+: llm_factory(model, client=...) + InstructorLLM
- ragas 0.2.x: langchain ChatOpenAI
"""

import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


class ZhipuLLMUnavailable(RuntimeError):
    """智谱 LLM 不可用（key 缺失 / 包缺失）"""


def create_zhipu_client(async_client: bool = True):
    """创建 OpenAI 客户端指向智谱兼容端点

    Args:
        async_client: True 返回 AsyncOpenAI，False 返回 OpenAI
    """
    settings = get_settings()
    if not settings.zhipu_api_key:
        raise ZhipuLLMUnavailable("未配置 ZHIPU_API_KEY，请在 .env 中设置")

    try:
        from openai import AsyncOpenAI, OpenAI
    except ImportError as e:
        raise ZhipuLLMUnavailable("缺少 openai 包，请运行: pip install openai") from e

    client_cls = AsyncOpenAI if async_client else OpenAI
    return client_cls(
        api_key=settings.zhipu_api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        timeout=settings.llm_timeout_s,
        max_retries=0,  # 由 ragas/tenacity 层控制重试
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def create_zhipu_llm():
    """创建智谱 LLM 实例（兼容 ragas 0.2.x 和 0.4+）

    Returns:
        ragas llm 实例

    Raises:
        ZhipuLLMUnavailable: 配置缺失
    """
    settings = get_settings()
    if not settings.zhipu_api_key:
        raise ZhipuLLMUnavailable("未配置 ZHIPU_API_KEY，请在 .env 中设置")

    # 优先尝试 ragas 0.4+ 的 llm_factory(client=...)
    try:
        from ragas.llms import llm_factory
        client = create_zhipu_client(async_client=True)
        llm = llm_factory(settings.llm_model, client=client)
        logger.info("智谱 LLM 已初始化（ragas 0.4+ 模式，%s）", settings.llm_model)
        return llm
    except TypeError:
        pass  # ragas 0.2.x 不支持 client 参数，走下面的 fallback

    # ragas 0.2.x fallback：用 langchain ChatOpenAI
    try:
        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper
    except ImportError as e:
        raise ZhipuLLMUnavailable("缺少 langchain-openai 或 ragas 包") from e

    # Monkey-patch: 修复 ragas 的 temperature 与智谱 API 不兼容问题
    # 智谱 API 限制 temperature 最多 2 位小数，ragas 默认用 1e-8
    import functools
    _original_agenerate = LangchainLLMWrapper.agenerate_text
    @functools.wraps(_original_agenerate)
    async def _fixed_agenerate(self, prompt, n=1, temperature=None, **kwargs):
        if temperature is not None:
            temperature = round(float(temperature), 2)
        else:
            temperature = 0.0 if n == 1 else 0.30
        return await _original_agenerate(self, prompt, n=n, temperature=temperature, **kwargs)
    LangchainLLMWrapper.agenerate_text = _fixed_agenerate

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.zhipu_api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        max_tokens=8192,
        temperature=0,
    )
    logger.info("智谱 LLM 已初始化（ragas 0.2.x 模式，%s）", settings.llm_model)
    return llm


def create_zhipu_embeddings():
    """创建智谱 Embeddings 实例（兼容 ragas 0.2.x）

    Returns:
        langchain OpenAIEmbeddings 实例，指向智谱兼容端点
    """
    settings = get_settings()
    if not settings.zhipu_api_key:
        raise ZhipuLLMUnavailable("未配置 ZHIPU_API_KEY，请在 .env 中设置")

    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError as e:
        raise ZhipuLLMUnavailable("缺少 langchain-openai 包") from e

    emb = OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.zhipu_api_key,
        openai_api_base="https://open.bigmodel.cn/api/paas/v4/",
    )
    logger.info("智谱 Embeddings 已初始化（%s）", settings.embedding_model)
    return emb
