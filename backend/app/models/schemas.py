"""Pydantic 数据模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class Question(BaseModel):
    """面试题统一数据格式"""
    id: str = Field(description="唯一标识")
    question: str = Field(description="题目文本")
    answer: str = Field(description="参考答案")
    category: str = Field(description="分类")
    difficulty: str = Field(default="中等", description="难度：简单/中等/困难")
    source: str = Field(description="来源（文件名/URL）")
    tags: list[str] = Field(default_factory=list, description="标签")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class QueryRequest(BaseModel):
    """查询请求"""
    question: str = Field(min_length=1, max_length=1000, description="用户问题")
    conversation_id: str | None = Field(default=None, description="对话 ID（多轮对话）")
    chat_history: list[dict] | None = Field(default=None, description="对话历史")
    stream: bool = Field(default=False, description="是否流式返回")


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str = Field(description="回答内容")
    sources: list["SourceRef"] = Field(default_factory=list, description="来源引用")
    conversation_id: str = Field(description="对话 ID")


class SourceRef(BaseModel):
    """来源引用"""
    question_id: str = Field(description="题目 ID")
    question_text: str = Field(description="题目文本")
    score: float = Field(description="相关度分数")
    category: str = Field(description="分类")


class IngestRequest(BaseModel):
    """导入请求"""
    source: str = Field(description="数据来源：文件路径或 URL")
    source_type: str = Field(description="来源类型：md/pdf/url")


class IngestResponse(BaseModel):
    """导入响应"""
    ingested: int = Field(description="导入数量")
    duplicates: int = Field(description="重复数量")
    errors: int = Field(description="错误数量")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    vector_count: int = Field(description="向量数量")
    llm_status: str = Field(description="LLM 连接状态")


class StatsResponse(BaseModel):
    """统计响应"""
    total_questions: int = Field(description="总题目数")
    categories: dict[str, int] = Field(description="各分类数量")
    last_updated: str | None = Field(description="最后更新时间")


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(description="错误描述")
    status_code: int = Field(description="HTTP 状态码")
