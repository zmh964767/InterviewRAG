/**
 * useKnowledgeBase 单元测试
 *
 * 覆盖场景：
 * - 初始加载调用 listQuestions
 * - setQ debounce 300ms
 * - 筛选变化重置到第 1 页
 * - removeItem / insertItem 乐观更新
 * - 错误处理
 * - unmount 清理 debounce timer
 */

import { describe, test, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useKnowledgeBase } from '@/hooks/useKnowledgeBase'
import type { QuestionListResponse } from '@/lib/types'

// ---------- Mock api ----------

const listQuestionsMock = vi.fn()

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    listQuestions: (...args: unknown[]) => listQuestionsMock(...args),
  }
})

function makeResponse(overrides: Partial<QuestionListResponse> = {}): QuestionListResponse {
  return {
    items: [
      { id: 'q1', question: '什么是 Transformer?', answer: '注意力机制...', category: '深度学习', difficulty: '中等', source: 'manual', tags: [], created_at: '2025-01-01T00:00:00' },
      { id: 'q2', question: '什么是 RAG?', answer: '检索增强...', category: 'RAG', difficulty: '简单', source: 'manual', tags: [], created_at: '2025-01-02T00:00:00' },
    ],
    total: 2,
    page: 1,
    size: 20,
    categories: ['深度学习', 'RAG'],
    ...overrides,
  }
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  listQuestionsMock.mockReset()
  listQuestionsMock.mockResolvedValue(makeResponse())
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

// ---------- Tests ----------

describe('useKnowledgeBase', () => {
  test('初始加载调用 listQuestions', async () => {
    const { result } = renderHook(() => useKnowledgeBase())

    await waitFor(() => {
      expect(listQuestionsMock).toHaveBeenCalledTimes(1)
    })
    expect(result.current.items).toHaveLength(2)
    expect(result.current.total).toBe(2)
    expect(result.current.categories).toEqual(['深度学习', 'RAG'])
  })

  test('setQ debounce 300ms', async () => {
    const { result } = renderHook(() => useKnowledgeBase())

    // 等初始加载完成
    await waitFor(() => expect(listQuestionsMock).toHaveBeenCalledTimes(1))

    // 设置搜索词
    act(() => { result.current.setQ('transformer') })

    // 300ms 内不应发起新请求
    await act(async () => { await vi.advanceTimersByTimeAsync(200) })
    expect(listQuestionsMock).toHaveBeenCalledTimes(1)

    // 300ms 后应发起新请求
    await act(async () => { await vi.advanceTimersByTimeAsync(150) })
    expect(listQuestionsMock).toHaveBeenCalledTimes(2)
    expect(listQuestionsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: 'transformer' }),
    )
  })

  test('筛选变化重置到第 1 页', async () => {
    listQuestionsMock.mockResolvedValue(makeResponse({ page: 2, total: 40 }))
    const { result } = renderHook(() => useKnowledgeBase())

    await waitFor(() => expect(listQuestionsMock).toHaveBeenCalledTimes(1))

    // 改分类
    act(() => { result.current.setCategory('RAG') })

    // 应重置 page 到 1
    expect(result.current.page).toBe(1)
  })

  test('removeItem 乐观删除', async () => {
    const { result } = renderHook(() => useKnowledgeBase())

    await waitFor(() => expect(result.current.items).toHaveLength(2))

    act(() => { result.current.removeItem('q1') })

    expect(result.current.items).toHaveLength(1)
    expect(result.current.items[0].id).toBe('q2')
    expect(result.current.total).toBe(1)
  })

  test('insertItem 乐观插入到头部', async () => {
    const { result } = renderHook(() => useKnowledgeBase())

    await waitFor(() => expect(result.current.items).toHaveLength(2))

    act(() => {
      result.current.insertItem({
        id: 'q3', question: '新题', answer: '答案', category: 'test',
        difficulty: '简单', source: 'manual', tags: [], created_at: '2025-01-03T00:00:00',
      })
    })

    expect(result.current.items).toHaveLength(3)
    expect(result.current.items[0].id).toBe('q3')
    expect(result.current.total).toBe(3)
  })

  test('请求错误设置 error', async () => {
    listQuestionsMock.mockRejectedValue(new Error('网络超时'))
    const { result } = renderHook(() => useKnowledgeBase())

    await waitFor(() => {
      expect(result.current.error).toBe('网络超时')
      expect(result.current.isLoading).toBe(false)
    })
  })

  test('unmount 时清理 debounce timer', async () => {
    const { result, unmount } = renderHook(() => useKnowledgeBase())

    await waitFor(() => expect(listQuestionsMock).toHaveBeenCalledTimes(1))

    act(() => { result.current.setQ('test') })
    unmount()

    // 推进时间不应再触发新请求
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    // 仍为初始加载的 1 次调用
    expect(listQuestionsMock).toHaveBeenCalledTimes(1)
  })
})
