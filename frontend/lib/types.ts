/** API 类型定义
 *
 * 后端 schema 来源: backend/app/models/schemas.py
 * 保持字段名与后端 snake_case 一致（Next.js API routes 直接透传）。
 */

export interface QueryRequest {
  question: string
  conversation_id?: string
  chat_history?: Array<{ role: string; content: string }>
  stream?: boolean
}

/** @see backend/app/models/schemas.py SourceRef */
export interface SourceRef {
  question_id: string
  question_text: string
  answer_text: string
  score: number
  category: string
}

/** @see backend/app/models/schemas.py QueryResponse */
export interface QueryResponse {
  answer: string
  sources: SourceRef[]
  conversation_id: string
}

export interface IngestRequest {
  source: string
  source_type: 'md' | 'pdf' | 'url'
}

export interface IngestResponse {
  ingested: number
  duplicates: number
  errors: number
}

export interface HealthResponse {
  status: string
  vector_count: number
  llm_status: string
}

export interface StatsResponse {
  total_questions: number
  categories: Record<string, number>
  last_updated: string | null
}

export interface ErrorResponse {
  detail: string
  status_code: number
}

/** 前端消息类型 */
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceRef[]
  timestamp: number
  /** 所属对话 ID(feedback 提交需要) */
  conversationId?: string
}

/** SSE 流式事件 */
export interface StreamEvent {
  content?: string
  done?: boolean
  conversation_id?: string
  sources?: SourceRef[]
  error?: string
}

// =========================================================================
// 知识库管理
// =========================================================================

/** @see backend/app/models/schemas.py Question */
export interface Question {
  id: string
  question: string
  answer: string
  category: string
  difficulty: string
  source: string
  tags: string[]
  created_at: string
}

export interface QuestionListRequest {
  page?: number
  size?: number
  q?: string
  category?: string
  difficulty?: string
}

export interface QuestionListResponse {
  items: Question[]
  total: number
  page: number
  size: number
  categories: string[]
}

export interface DeleteQuestionResponse {
  deleted: boolean
  id: string
}

export interface InsertOneRequest {
  question: string
  answer: string
  category?: string
  difficulty?: string
  source?: string
}

/** @see backend/app/models/schemas.py TaskStatusResponse */
export type TaskStatus = 'pending' | 'running' | 'done' | 'failed'

/** @see backend/app/models/schemas.py TaskStatusResponse */
export interface TaskStatusResponse {
  task_id: string
  status: TaskStatus
  source_type: string
  source: string
  total: number
  done: number
  ingested: number
  duplicates: number
  errors: number
  started_at: string
  finished_at: string | null
  error_message: string | null
}

export interface TaskListResponse {
  tasks: TaskStatusResponse[]
}

export interface IngestTaskAccepted {
  task_id: string
}

// =========================================================================
// 评估报告
// =========================================================================

/** 评估 RAGAS 指标 */
export interface EvalMetrics {
  faithfulness: number
  answer_relevancy: number
  context_precision: number
  context_recall: number
}

/** 评估汇总条目（latest_summary 或 history 快照） */
export interface EvalSummaryItem {
  metrics: EvalMetrics
  timestamp: string
  total: number
  error_count: number
}

/** /api/eval/summary 响应 */
export interface EvalSummaryResponse {
  latest: EvalSummaryItem | null
  history: EvalSummaryItem[]
}

/** 检索策略对比（单个策略） */
export interface EvalComparisonPlan {
  'hit_rate@5': number
  mrr: number
}

/** 单题评估结果 */
export interface EvalItemResult {
  id: string
  question: string
  answer: string
  metrics: Record<string, number>
  error?: string | null
}

/** /api/eval/detail 响应 */
export interface EvalDetailResponse {
  timestamp?: string
  aggregated: EvalMetrics
  errors: string[]
  total: number
  items?: EvalItemResult[]
  comparison: Record<string, EvalComparisonPlan>
}

/** 触发评估请求 */
export interface RunEvalRequest {
  mode: 'full' | 'ragas' | 'comparison' | 'sanity'
}

/** 触发评估响应 */
export interface RunEvalResponse {
  task_id: string
}

// =========================================================================
// 评估快照对比
// =========================================================================

/** 方向类型 */
export type MetricDirection = 'up' | 'down' | 'same'

/** 单个指标的 base/target 对比 */
export interface MetricDiff {
  name: 'faithfulness' | 'answer_relevancy' | 'context_precision' | 'context_recall'
  base: number
  target: number
  change: number
  direction: MetricDirection
}

/** 快照元信息(用于 base/target 选择器) */
export interface CompareSnapshotInfo {
  timestamp: string
  total: number
  error_count: number
  metrics: EvalMetrics
}

/** /api/admin/eval/compare 响应 */
export interface CompareResponse {
  base: CompareSnapshotInfo
  target: CompareSnapshotInfo
  diffs: MetricDiff[]
  improved: number
  regressed: number
  same: number
}

// =========================================================================
// Sweep 参数扫描
// =========================================================================

/** sweep 组合单行(只含 E 和 B 两个策略) */
export interface SweepRow {
  type: 'prompt' | 'chunk'
  prompt_variant: number | null
  chunk_size: number | null
  E_hr5: number
  E_mrr: number
  B_hr5: number
  B_mrr: number
  duration_s: number | null
}

/** /api/admin/eval/sweep 响应 */
export interface SweepResponse {
  rows: SweepRow[]
  winner: SweepRow | null
  /** 从 latest_summary.json 动态读取的基准,文件/字段缺失时为 0.0 */
  baseline_e_hr5: number
}

// =========================================================================
// 用户反馈
// =========================================================================

/** 公开端 POST /api/feedback 请求体 */
export interface SubmitFeedbackBody {
  message_id: string
  conversation_id: string
  rating: 1 | -1
  comment?: string | null
  message_content: string
  message_role: 'user' | 'assistant'
}

/** 管理端单条反馈 */
export interface FeedbackItem {
  id: string
  message_id: string
  conversation_id: string
  rating: 1 | -1
  comment: string | null
  message_content: string
  message_role: 'user' | 'assistant'
  client_ip: string | null
  user_agent: string | null
  created_at: string
}

/** GET /api/admin/feedback 响应 */
export interface FeedbackListResponse {
  items: FeedbackItem[]
  total: number
  page: number
  size: number
}

/** GET /api/admin/feedback/stats 响应 */
export interface FeedbackStats {
  positive: number
  negative: number
  total: number
  rate: number
}
