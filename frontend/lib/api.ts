/** API 调用封装 */

import type {
  QueryRequest,
  QueryResponse,
  IngestRequest,
  IngestResponse,
  HealthResponse,
  StatsResponse,
  StreamEvent,
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
