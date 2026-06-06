/** API 类型定义 */

export interface QueryRequest {
  question: string
  conversation_id?: string
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
