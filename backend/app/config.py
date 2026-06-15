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
    bm25_refresh_ttl_seconds: float = 30.0  # BM25 懒刷新 TTL（秒），dirty 标记后冷却期

    # Query 改写（多路召回合并）
    multi_query_enabled: bool = True   # kill switch：False 时退化为单路混合检索
    multi_query_n: int = 3             # 改写变体数（含原 query 共 N 个）
    multi_query_timeout_s: float = 5.0  # 改写 LLM 超时；超时回退原 query
    query_rewrite_prompt_variant: int = 1  # Prompt 变体 1..5（见 prompts/query_rewrite_v*.txt）

    # LLM 参数
    llm_model: str = "glm-4-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 8192
    llm_timeout_s: float = 30.0  # LLM API 调用超时；超时抛 ExternalServiceError

    # Embedding 参数
    embedding_model: str = "embedding-3"

    # 对话记忆
    memory_window: int = 10
    max_conversations: int = 100

    # CORS（逗号分隔的域名列表，如 "http://localhost:3000,https://example.com"）
    # dev 模式加 :3004 是因为 Next.js dev server 3000 端口常被占用，前端会跑到 3001~3004。
    # 生产部署前应改为具体域名。
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
    ]

    # Provider 选择
    llm_provider: str = "zhipu"           # "zhipu" | "openai"
    embedding_provider: str = "zhipu"     # "zhipu" | "openai"

    # OpenAI 兼容端点（llm/embedding_provider="openai" 时启用）
    openai_api_key: str = ""
    openai_base_url: str = ""             # 空字串 → OpenAI client 传 None（即官方默认）
    openai_llm_model: str = ""            # 覆盖 llm_model，空字串时 fallback 到 llm_model
    openai_embedding_model: str = ""      # 覆盖 embedding_model，空字串时 fallback 到 embedding_model

    # 管理员认证（生产环境务必通过 ADMIN_PASSWORD 环境变量设置）
    admin_password: str = ""
    jwt_secret_key: str = ""  # 空值时由 app.auth 模块启动时自动生成
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 小时
    # Cookie secure 标志：dev http 设为 False，部署到 https 时必须设 True
    cookie_secure: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
