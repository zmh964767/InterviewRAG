"""Pydantic 数据模型"""

from datetime import datetime
from typing import Literal
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


# =========================================================================
# 知识库管理 UI
# =========================================================================


class QuestionListResponse(BaseModel):
    """题目列表响应"""
    items: list[Question] = Field(default_factory=list, description="题目列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页（1-based）")
    size: int = Field(description="页大小")
    categories: list[str] = Field(default_factory=list, description="所有分类")


class InsertOneRequest(BaseModel):
    """单条插入请求（撤销机制用）"""
    question: str = Field(min_length=1, description="题面")
    answer: str = Field(min_length=1, description="参考答案")
    category: str = Field(default="未分类", description="分类")
    difficulty: str = Field(default="中等", description="难度")
    source: str = Field(default="manual", description="来源标识")


class IngestTaskAccepted(BaseModel):
    """异步导入任务已受理"""
    task_id: str = Field(description="任务 ID")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str = Field(description="pending|running|done|failed")
    source_type: str
    source: str
    total: int = 0
    done: int = 0
    ingested: int = 0
    duplicates: int = 0
    errors: int = 0
    started_at: str = ""
    finished_at: str | None = None
    error_message: str | None = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: list[TaskStatusResponse] = Field(default_factory=list)


class DeleteQuestionResponse(BaseModel):
    """删除响应"""
    deleted: bool
    id: str


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(description="错误描述")
    status_code: int = Field(description="HTTP 状态码")


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    ids: list[str]


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""
    deleted: int


class UpdateQuestionRequest(BaseModel):
    """更新题目请求"""
    question: str | None = None
    answer: str | None = None
    category: str | None = None
    difficulty: str | None = None


# =========================================================================
# 评估快照对比
# =========================================================================

class MetricDiff(BaseModel):
    """单个指标的 base/target 对比"""
    name: str = Field(description="指标名: faithfulness|answer_relevancy|context_precision|context_recall")
    base: float = Field(description="base 快照的指标值")
    target: float = Field(description="target 快照的指标值")
    change: float = Field(description="target - base")
    direction: str = Field(description="变化方向: up|down|same")


class CompareResponse(BaseModel):
    """两个评估快照的对比响应"""
    base: dict = Field(description="base 快照元信息: timestamp/total/error_count/metrics")
    target: dict = Field(description="target 快照元信息")
    diffs: list[MetricDiff] = Field(default_factory=list, description="逐指标 diff")
    improved: int = Field(description="上升的指标数")
    regressed: int = Field(description="下降的指标数")
    same: int = Field(description="持平的指标数")


# =========================================================================
# Sweep 参数扫描
# =========================================================================

class SweepRow(BaseModel):
    """单个 sweep 组合的结果(只取 E 和 B 两个策略)"""
    type: str = Field(description="prompt | chunk")
    prompt_variant: int | None = Field(default=None, description="prompt variant 编号(1..5),chunk sweep 时为该次扫描使用的 variant")
    chunk_size: int | None = Field(default=None, description="chunk size,prompt sweep 时为该次扫描使用的 chunk size")
    E_hr5: float = Field(description="E_多路改写混合 策略的 hit_rate@5")
    E_mrr: float = Field(description="E_多路改写混合 策略的 mrr")
    B_hr5: float = Field(description="B_混合检索 策略的 hit_rate@5")
    B_mrr: float = Field(description="B_混合检索 策略的 mrr")
    duration_s: float | None = Field(default=None, description="本次扫描耗时(秒)")


class SweepResponse(BaseModel):
    """sweep 全部组合 + winner"""
    rows: list[SweepRow] = Field(default_factory=list, description="所有 sweep 组合,按文件读取顺序")
    winner: SweepRow | None = Field(default=None, description="E_hr5 最高的组合")
    baseline_e_hr5: float = Field(default=0.0, description="最新评估汇总里的基准 E_hr5(从 latest_summary.json 动态读,文件/字段缺失时为 0.0)")


# =========================================================================
# 用户反馈
# =========================================================================

class SubmitFeedbackRequest(BaseModel):
    """用户提交反馈(公开端)"""
    message_id: str = Field(min_length=1, max_length=64, description="前端 message.id")
    conversation_id: str = Field(min_length=1, max_length=64, description="对话 ID")
    rating: Literal[1, -1] = Field(description="1=👍, -1=👎")
    comment: str | None = Field(default=None, max_length=1000, description="可选 comment")
    message_content: str = Field(min_length=1, max_length=10000, description="消息内容快照")
    message_role: Literal["user", "assistant"] = Field(description="user | assistant")


class FeedbackItem(BaseModel):
    """单条反馈(管理端列表项)"""
    id: str
    message_id: str
    conversation_id: str
    rating: int
    comment: str | None
    message_content: str
    message_role: str
    client_ip: str | None
    user_agent: str | None
    created_at: str


class FeedbackListResponse(BaseModel):
    """反馈列表响应"""
    items: list[FeedbackItem] = Field(default_factory=list)
    total: int
    page: int
    size: int


class FeedbackStats(BaseModel):
    """反馈统计"""
    positive: int = Field(description="👍 数量")
    negative: int = Field(description="👎 数量")
    total: int = Field(description="总反馈数")
    rate: float = Field(description="差评率: negative / total(0..1)")
