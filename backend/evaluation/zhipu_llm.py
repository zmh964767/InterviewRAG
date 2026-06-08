"""智谱 LLM 适配层

将智谱 GLM API 包装为 langchain ChatOpenAI，
供 RAGAS 0.1.x 评估的 LLM judge 使用。

原理：智谱提供 OpenAI 兼容端点 https://open.bigmodel.cn/api/paas/v4/
只要传 base_url 即可用 ChatOpenAI 调智谱。
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def create_zhipu_llm(temperature: float = 0.0, max_tokens: int = 4096):
    """创建智谱 LLM 实例（OpenAI 兼容模式）

    Args:
        temperature: 0.0 保证评估结果可复现
        max_tokens: RAGAS judge 需要较长输出

    Returns:
        配置好的 langchain ChatOpenAI 实例

    Raises:
        ZhipuLLMUnavailable: 配置缺失或 langchain-openai 未安装
    """
    settings = get_settings()
    if not settings.zhipu_api_key:
        raise ZhipuLLMUnavailable("未配置 ZHIPU_API_KEY，请在 .env 中设置")

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise ZhipuLLMUnavailable(
            "缺少 langchain-openai 包，请运行: pip install langchain-openai"
        ) from e

    llm = ChatOpenAI(
        model=settings.llm_model,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key=settings.zhipu_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=180,
    )
    logger.info(f"智谱 LLM 已初始化（{settings.llm_model}）")
    return llm
