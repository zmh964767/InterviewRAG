"""智谱 LLM 适配层

RAGAS 0.4.3 collections metrics 要求用 llm_factory + InstructorLLM，
不接受 langchain ChatOpenAI。因此：
- ZhipuOpenAIClient: 用 openai.OpenAI 指向智谱兼容端点
- create_zhipu_llm(): 返回 llm_factory(llm, client) 的 InstructorLLM 实例
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
    """创建智谱 LLM 实例（RAGAS 0.4+ InstructorLLM 接口）

    Returns:
        ragas.llms.base.BaseRagasLLM 实例，可直接传给 RAGAS metrics

    Raises:
        ZhipuLLMUnavailable: 配置缺失
    """
    try:
        from ragas.llms import llm_factory
    except ImportError as e:
        raise ZhipuLLMUnavailable(
            "缺少 ragas 包，请运行: pip install ragas"
        ) from e

    client = create_zhipu_client()
    settings = get_settings()

    llm = llm_factory(settings.llm_model, client=client)
    logger.info(f"智谱 LLM 已初始化（{settings.llm_model}）")
    return llm
