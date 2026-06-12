/** API 调用封装 */

import type {
  QueryRequest,
  QueryResponse,
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
  EvalSummaryResponse,
  EvalDetailResponse,
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
  signal?: AbortSignal,
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
    signal,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('无法读取响应流')

  const decoder = new TextDecoder()
  let buffer = ''
  let aborted = false

  // 监听 abort 信号，主动 cancel reader（避免 reader.read() 在 abort 后继续读到 stale 帧）
  // cancel 让 reader 干净结束（done=true 不抛错），但我们要让上游感知到 abort 状态
  if (signal) {
    signal.addEventListener('abort', () => {
      aborted = true
      reader.cancel().catch(() => {})
    }, { once: true })
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    // abort 后 reader 仍可能返回最后几个 chunk，主动丢弃
    if (aborted) continue

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

  // abort 后读循环正常结束（done=true），但我们需要告诉调用方"这是被中断的"
  if (aborted) {
    const err = new Error('Aborted')
    err.name = 'AbortError'
    throw err
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

/** 健康检查 */
export async function healthCheck(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`)
  return res.json()
}

// =========================================================================
// 知识库管理（公开只读）
// =========================================================================

/** 题目列表查询（公开） */
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

// =========================================================================
// 管理端 API（带 JWT token）
// =========================================================================

function adminHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_token') : null
  const h: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) (h as Record<string, string>)['Authorization'] = `Bearer ${token}`
  return h
}

/** 管理端：题目列表（功能同公开，但走 /api/admin/） */
export async function adminListQuestions(
  request: QuestionListRequest = {},
): Promise<QuestionListResponse> {
  const params = new URLSearchParams()
  if (request.page) params.set('page', String(request.page))
  if (request.size) params.set('size', String(request.size))
  if (request.q) params.set('q', request.q)
  if (request.category) params.set('category', request.category)
  if (request.difficulty) params.set('difficulty', request.difficulty)

  const res = await fetch(`${API_BASE}/api/admin/questions?${params.toString()}`, { headers: adminHeaders() })
  if (!res.ok) throw new Error(`列表查询失败: HTTP ${res.status}`)
  return res.json()
}

/** 管理端：删除题目 */
export async function adminDeleteQuestion(id: string): Promise<DeleteQuestionResponse> {
  const res = await fetch(`${API_BASE}/api/admin/questions/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: adminHeaders(),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '删除失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 管理端：批量删除题目 */
export async function adminBatchDelete(ids: string[]): Promise<{ deleted: number }> {
  const res = await fetch(`${API_BASE}/api/admin/questions/batch-delete`, {
    method: 'POST',
    headers: adminHeaders(),
    body: JSON.stringify({ ids }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '批量删除失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 管理端：统计 */
export async function adminGetStats(signal?: AbortSignal): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/api/admin/stats`, {
    headers: adminHeaders(),
    signal,
  })
  if (!res.ok) throw new Error('统计查询失败')
  return res.json()
}

/** 管理端：单条插入 */
export async function adminInsertOne(request: InsertOneRequest): Promise<Question> {
  const res = await fetch(`${API_BASE}/api/admin/ingest/insert-one`, {
    method: 'POST',
    headers: adminHeaders(),
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '插入失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 管理端：提交异步导入任务 */
export async function adminSubmitIngestTask(
  source: string,
  sourceType: 'md' | 'pdf' | 'url',
): Promise<IngestTaskAccepted> {
  const res = await fetch(`${API_BASE}/api/admin/ingest`, {
    method: 'POST',
    headers: adminHeaders(),
    body: JSON.stringify({ source, source_type: sourceType }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '任务提交失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 管理端：上传文件导入 */
export async function adminUploadIngestFile(file: File): Promise<IngestTaskAccepted> {
  const token = localStorage.getItem('admin_token')
  const headers: HeadersInit = {}
  if (token) (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`

  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/api/admin/ingest/upload`, {
    method: 'POST',
    headers,
    body: formData,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '上传失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 管理端：评估汇总 */
export async function adminGetEvalSummary(signal?: AbortSignal): Promise<EvalSummaryResponse> {
  const res = await fetch(`${API_BASE}/api/admin/eval/summary`, {
    headers: adminHeaders(),
    signal,
  })
  if (!res.ok) throw new Error('Failed to fetch eval summary')
  return res.json()
}

/** 管理端：评估详情 */
export async function adminGetEvalDetail(ts?: string): Promise<EvalDetailResponse> {
  const url = ts
    ? `${API_BASE}/api/admin/eval/detail?ts=${encodeURIComponent(ts)}`
    : `${API_BASE}/api/admin/eval/detail`
  const res = await fetch(url, { headers: adminHeaders() })
  if (!res.ok) throw new Error('Failed to fetch eval detail')
  return res.json()
}

/** 管理端：查询任务状态 */
export async function adminGetTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const res = await fetch(`${API_BASE}/api/admin/ingest/tasks/${encodeURIComponent(taskId)}`, { headers: adminHeaders() })
  if (!res.ok) throw new Error(`任务查询失败: HTTP ${res.status}`)
  return res.json()
}

/** 管理端：列出未完成任务 */
export async function adminListActiveTasks(): Promise<TaskListResponse> {
  const res = await fetch(`${API_BASE}/api/admin/ingest/tasks`, { headers: adminHeaders() })
  if (!res.ok) throw new Error(`任务列表查询失败: HTTP ${res.status}`)
  return res.json()
}

/** 管理端：修改管理员密码 */
export async function adminChangePassword(
  currentPassword: string,
  newPassword: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/admin/change-password`, {
    method: 'POST',
    headers: adminHeaders(),
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '修改失败' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
