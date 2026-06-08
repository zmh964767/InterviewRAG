"""应用配置管理"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置，从环境变量读取"""

    # 智谱 API
    zhipu_api_key: str = ""

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"

    # SQLite
    sqlite_db_path: str = "./data/interview.db"

    # 数据目录
    raw_data_dir: str = "./data/raw"
    processed_data_dir: str = "./data/processed"

    # RAG 参数
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 20
    rerank_top_k: int = 5
    bm25_weight: float = 0.3  # BM25 权重，向量权重 = 1 - bm25_weight

    # LLM 参数
    llm_model: str = "glm-4-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 8192

    # Embedding 参数
    embedding_model: str = "embedding-3"

    # 对话记忆
    memory_window: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
