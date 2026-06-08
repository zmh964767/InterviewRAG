/** API 类型定义 */

export interface QueryRequest {
  question: string
  conversation_id?: string
  chat_history?: Array<{ role: string; content: string }>
  stream?: boolean
}

export interface SourceRef {
  question_id: string
  question_text: string
  score: number
  category: string
}

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

export type TaskStatus = 'pending' | 'running' | 'done' | 'failed'

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
