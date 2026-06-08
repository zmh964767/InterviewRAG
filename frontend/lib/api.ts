/** API 调用封装 */

import type {
  QueryRequest,
  QueryResponse,
  IngestRequest,
  IngestResponse,
  HealthResponse,
  StatsResponse,
  StreamEvent,
  Question,
  QuestionListRequest,
  QuestionListResponse,
  DeleteQuestionResponse,
  InsertOneRequest,
  TaskStatusResponse,
  TaskListResponse,
  IngestTaskAccepted,
} from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

/** 普通查询 */
export async function query(request: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: false }),
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

/** 流式查询（SSE） */
export async function* queryStream(
  question: string,
  conversationId?: string,
  chatHistory?: Array<{ role: string; content: string }>,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      chat_history: chatHistory,
      stream: true,
    }),
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('无法读取响应流')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event: StreamEvent = JSON.parse(line.slice(6))
          yield event
        } catch {
          // 忽略解析错误
        }
      }
    }
  }

  // 处理剩余 buffer
  if (buffer.startsWith('data: ')) {
    try {
      const event: StreamEvent = JSON.parse(buffer.slice(6))
      yield event
    } catch {
      // 忽略
    }
  }
}

/** 导入数据 */
export async function ingest(request: IngestRequest): Promise<IngestResponse> {
  const res = await fetch(`${API_BASE}/api/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '导入失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

/** 健康检查 */
export async function healthCheck(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`)
  return res.json()
}

/** 知识库统计 */
export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/api/stats`)
  return res.json()
}

// =========================================================================
// 知识库管理
// =========================================================================

/** 题目列表查询 */
export async function listQuestions(
  request: QuestionListRequest = {},
): Promise<QuestionListResponse> {
  const params = new URLSearchParams()
  if (request.page) params.set('page', String(request.page))
  if (request.size) params.set('size', String(request.size))
  if (request.q) params.set('q', request.q)
  if (request.category) params.set('category', request.category)
  if (request.difficulty) params.set('difficulty', request.difficulty)

  const url = `${API_BASE}/api/questions?${params.toString()}`
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`列表查询失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 删除单条题目 */
export async function deleteQuestion(id: string): Promise<DeleteQuestionResponse> {
  const res = await fetch(`${API_BASE}/api/questions/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '删除失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 单条插入（撤销机制用） */
export async function insertOne(request: InsertOneRequest): Promise<Question> {
  const res = await fetch(`${API_BASE}/api/ingest/insert-one`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '插入失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 查询任务状态 */
export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const res = await fetch(`${API_BASE}/api/ingest/tasks/${encodeURIComponent(taskId)}`)
  if (!res.ok) {
    throw new Error(`任务查询失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 列出未完成任务 */
export async function listActiveTasks(): Promise<TaskListResponse> {
  const res = await fetch(`${API_BASE}/api/ingest/tasks`)
  if (!res.ok) {
    throw new Error(`任务列表查询失败: HTTP ${res.status}`)
  }
  return res.json()
}

/** 提交异步导入任务（md/pdf/url） */
export async function submitIngestTask(
  source: string,
  sourceType: 'md' | 'pdf' | 'url',
): Promise<IngestTaskAccepted> {
  const res = await fetch(`${API_BASE}/api/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, source_type: sourceType }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '任务提交失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 上传文件导入 */
export async function uploadIngestFile(file: File): Promise<IngestTaskAccepted> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/api/ingest/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '上传失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
