"""智谱 Embedding 服务封装"""

import logging

from zhipuai import ZhipuAI

from app.config import get_settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class EmbedService:
    """智谱 Embedding 服务"""

    def __init__(self):
        settings = get_settings()
        if not settings.zhipu_api_key:
            raise ExternalServiceError("智谱API", "未配置 ZHIPU_API_KEY")

        self.client = ZhipuAI(api_key=settings.zhipu_api_key)
        self.model = settings.embedding_model
        logger.info(f"智谱 Embedding 已初始化，模型: {self.model}")

    def embed_query(self, text: str) -> list[float]:
        """将文本转为向量"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding 调用失败: {e}")
            raise ExternalServiceError("智谱Embedding", str(e))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转为向量"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"批量 Embedding 调用失败: {e}")
            raise ExternalServiceError("智谱Embedding", str(e))
