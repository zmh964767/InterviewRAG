/**
 * ChatContext 单元测试
 *
 * 覆盖 implement.md §4 列出的所有场景：
 * - 基础 CRUD（create / switch / delete / rename / updateMessages）
 * - 持久化（localStorage 恢复 + 写入 debounce）
 * - 流式 partial 同步（核心）
 * - useConversations adapter 兼容性
 */

import { describe, test, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { ChatProvider, useChatContext } from '@/contexts/ChatContext'
import { useConversations } from '@/hooks/useConversations'
import type { StreamEvent } from '@/lib/types'

// ---------- Mock api.queryStream via vi.mock ----------

const queryStreamMock = vi.fn()

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    queryStream: (...args: unknown[]) => queryStreamMock(...args),
  }
})

function makeStream(chunks: Array<Partial<StreamEvent>>): AsyncGenerator<StreamEvent> {
  async function* gen() {
    for (const c of chunks) {
      yield c as StreamEvent
    }
  }
  return gen()
}

beforeEach(() => {
  queryStreamMock.mockReset()
  queryStreamMock.mockImplementation(() =>
    makeStream([
      { content: 'Hello' },
      { content: ' world' },
      { done: true, sources: [] },
    ]),
  )
})

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

// ---------- Test harness ----------

function makeWrapper() {
  return ({ children }: { children: ReactNode }) => (
    <ChatProvider>{children}</ChatProvider>
  )
}

// =====================================================================
// 基础 CRUD
// =====================================================================

describe('ChatContext - 基础 CRUD', () => {
  test('createConversation 创建新对话并设为 currentId + 返回 id', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let id = ''
    act(() => {
      id = result.current.createConversation()
    })

    expect(id).toBeTruthy()
    expect(result.current.conversations).toHaveLength(1)
    expect(result.current.conversations[0].id).toBe(id)
    expect(result.current.currentId).toBe(id)
    expect(result.current.currentConversation?.id).toBe(id)
    expect(result.current.currentMessages).toEqual([])
  })

  test('switchConversation 修改 currentId', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let id1 = ''
    let id2 = ''
    act(() => {
      id1 = result.current.createConversation()
      id2 = result.current.createConversation()
    })

    expect(result.current.currentId).toBe(id2)

    act(() => {
      result.current.switchConversation(id1)
    })
    expect(result.current.currentId).toBe(id1)
    expect(result.current.currentConversation?.id).toBe(id1)
  })

  test('deleteConversation 删除后切到下一个对话', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let id1 = ''
    let id2 = ''
    act(() => {
      id1 = result.current.createConversation()
      id2 = result.current.createConversation()
    })

    expect(result.current.conversations).toHaveLength(2)
    expect(result.current.currentId).toBe(id2)

    act(() => {
      result.current.deleteConversation(id1)
    })

    expect(result.current.conversations).toHaveLength(1)
    expect(result.current.conversations[0].id).toBe(id2)
    expect(result.current.currentId).toBe(id2)
  })

  test('deleteConversation 删除最后一个对话 -> 自动创建新空对话', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let id1 = ''
    act(() => {
      id1 = result.current.createConversation()
    })

    expect(result.current.conversations).toHaveLength(1)

    act(() => {
      result.current.deleteConversation(id1)
    })

    expect(result.current.conversations).toHaveLength(1)
    expect(result.current.conversations[0].id).not.toBe(id1)
    expect(result.current.currentId).toBe(result.current.conversations[0].id)
    expect(result.current.currentMessages).toEqual([])
  })

  test('deleteConversation 删除非当前对话时 currentId 不变', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let id1 = ''
    let id2 = ''
    act(() => {
      id1 = result.current.createConversation()
      id2 = result.current.createConversation()
    })
    // currentId is id2 (newest first)
    act(() => {
      result.current.deleteConversation(id1)
    })
    expect(result.current.currentId).toBe(id2)
    expect(result.current.conversations).toHaveLength(1)
  })

  test('renameConversation 修改标题', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let id = ''
    act(() => {
      id = result.current.createConversation()
    })

    act(() => {
      result.current.renameConversation(id, '新标题')
    })

    expect(result.current.conversations[0].title).toBe('新标题')
  })

  test('updateMessages 写入 messages + 标题为"新对话"时自动从首条 user 消息更新', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    act(() => {
      result.current.createConversation()
    })

    expect(result.current.conversations[0].title).toBe('新对话')

    const newMessages = [
      {
        id: 'm1',
        role: 'user' as const,
        content: '请解释一下 React hooks',
        timestamp: Date.now(),
      },
      {
        id: 'm2',
        role: 'assistant' as const,
        content: 'React hooks 是...',
        timestamp: Date.now(),
      },
    ]

    act(() => {
      result.current.updateMessages(newMessages)
    })

    expect(result.current.currentMessages).toEqual(newMessages)
    // MAX_TITLE_LENGTH = 15: '请解释一下 React hooks' -> '请解释一下 React hoo...'
    expect(result.current.conversations[0].title).toBe('请解释一下 React hoo...')
  })

  test('updateMessages 标题已自定义时不自动覆盖', async () => {
    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let id = ''
    act(() => {
      id = result.current.createConversation()
    })

    act(() => {
      result.current.renameConversation(id, '我的自定义标题')
    })

    act(() => {
      result.current.updateMessages([
        {
          id: 'm1',
          role: 'user' as const,
          content: '问点别的',
          timestamp: Date.now(),
        },
      ])
    })

    expect(result.current.conversations[0].title).toBe('我的自定义标题')
  })
})

// =====================================================================
// 持久化
// =====================================================================

describe('ChatContext - 持久化', () => {
  test('挂载时从 localStorage 恢复 conversations 和 currentId', async () => {
    const existing = [
      {
        id: 'c1',
        title: '恢复的对话',
        messages: [
          {
            id: 'm1',
            role: 'user' as const,
            content: '之前的消息',
            timestamp: 1,
          },
        ],
        createdAt: 1,
        updatedAt: 1,
      },
    ]
    localStorage.setItem('interviewrag_conversations', JSON.stringify(existing))
    localStorage.setItem('interviewrag_active_id', 'c1')

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(result.current.conversations).toHaveLength(1)
    })

    expect(result.current.conversations[0].title).toBe('恢复的对话')
    expect(result.current.currentId).toBe('c1')
    expect(result.current.currentMessages[0].content).toBe('之前的消息')
  })

  test('localStorage 中的 activeId 不存在时回退到第一个对话', async () => {
    const existing = [
      {
        id: 'c1',
        title: 'A',
        messages: [],
        createdAt: 1,
        updatedAt: 1,
      },
      {
        id: 'c2',
        title: 'B',
        messages: [],
        createdAt: 2,
        updatedAt: 2,
      },
    ]
    localStorage.setItem('interviewrag_conversations', JSON.stringify(existing))
    localStorage.setItem('interviewrag_active_id', 'nonexistent')

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(result.current.conversations).toHaveLength(2)
    })

    expect(result.current.currentId).toBe('c1')
  })

  test('每次 setConversations 触发 localStorage 写入（debounce 100ms）', async () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

      // Allow hydration to complete (it sets hasHydratedRef=true via useEffect)
      await act(async () => {
        await vi.runOnlyPendingTimersAsync()
      })

      act(() => {
        result.current.createConversation()
      })

      // Before debounce: the persistence useEffect schedules a 100ms timer
      // (but it short-circuits if !hasHydratedRef). After hydration completes
      // and a state change, the timer should fire after 100ms.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100)
      })

      const rawAfter = localStorage.getItem('interviewrag_conversations')
      expect(rawAfter).toBeTruthy()
      const parsed = JSON.parse(rawAfter!)
      expect(parsed).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })

  test('hydration guard：初次空 conversations 不会覆盖 localStorage 中已有数据', async () => {
    // Pre-existing data
    const existing = [
      {
        id: 'c1',
        title: '保留数据',
        messages: [],
        createdAt: 1,
        updatedAt: 1,
      },
    ]
    localStorage.setItem('interviewrag_conversations', JSON.stringify(existing))
    localStorage.setItem('interviewrag_active_id', 'c1')

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    // Wait for hydration to complete
    await waitFor(() => {
      expect(result.current.conversations).toHaveLength(1)
    })

    // After hydration completes, the existing data is preserved.
    expect(result.current.conversations[0].id).toBe('c1')
    expect(result.current.conversations[0].title).toBe('保留数据')
  })
})

// =====================================================================
// 流式 partial 同步（核心）
// =====================================================================

describe('ChatContext - 流式 partial 同步', () => {
  test('partial 更新 -> 实时合并到 conversations[partial.convId].messages', async () => {
    queryStreamMock.mockImplementation(() =>
      makeStream([
        { content: 'A' },
        { content: 'B' },
        { content: 'C' },
        { done: true, sources: [] },
      ]),
    )

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let convId = ''
    act(() => {
      convId = result.current.createConversation()
    })

    await act(async () => {
      await result.current.sendMessage('问题', convId)
    })

    const conv = result.current.conversations.find((c) => c.id === convId)!
    expect(conv.messages).toHaveLength(2)
    expect(conv.messages[0].role).toBe('user')
    expect(conv.messages[0].content).toBe('问题')
    expect(conv.messages[1].role).toBe('assistant')
    expect(conv.messages[1].content).toBe('ABC')
  })

  test('切对话中断当前流：旧流 abort，旧对话的 ai 消息停在切走时的 content', async () => {
    // Defer the stream by yielding one chunk at a time manually.
    let resolveNext: (() => void) | null = null
    const stream = (async function* () {
      yield { content: 'first' } as StreamEvent
      // wait until external signal
      await new Promise<void>((r) => {
        resolveNext = r
      })
      yield { content: ' second' } as StreamEvent
      yield { done: true, sources: [] } as StreamEvent
    })()
    queryStreamMock.mockImplementation(() => stream)

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let convA = ''
    let convB = ''
    act(() => {
      convA = result.current.createConversation()
      convB = result.current.createConversation()
    })
    // currentId is convB (newest first); switch back to convA
    act(() => {
      result.current.switchConversation(convA)
    })

    // Start streaming on convA
    let sendPromise: Promise<void> = Promise.resolve()
    act(() => {
      sendPromise = result.current.sendMessage('hello', convA)
    })

    // After first chunk: convA should already have user+partial-ai
    await waitFor(() => {
      const convAState = result.current.conversations.find((c) => c.id === convA)
      expect(convAState?.messages[1]?.content).toBe('first')
    })

    // Switch to convB mid-stream -> must abort the old stream
    act(() => {
      result.current.switchConversation(convB)
    })
    expect(result.current.currentId).toBe(convB)

    // Release the next chunk (should be ignored by the aborted stream)
    await act(async () => {
      resolveNext!()
      await sendPromise
    })

    // After switch + abort, convA's ai message content STAYS at 'first' —
    // the ' second' chunk is never written because the old stream was aborted.
    const convAAfter = result.current.conversations.find((c) => c.id === convA)!
    expect(convAAfter.messages[1].content).toBe('first')

    // convB should be untouched
    const convBAfter = result.current.conversations.find((c) => c.id === convB)!
    expect(convBAfter.messages).toEqual([])

    // lastError should be set with kind 'aborted' and bound to convA's ai message
    expect(result.current.lastError).not.toBeNull()
    expect(result.current.lastError?.kind).toBe('aborted')
    expect(result.current.lastError?.messageId).toBe(convAAfter.messages[1].id)
  })

  test('流完成 -> partial 保留为最后一个值（不重置为 null）', async () => {
    queryStreamMock.mockImplementation(() =>
      makeStream([
        { content: 'final' },
        { done: true, sources: [] },
      ]),
    )

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let convId = ''
    act(() => {
      convId = result.current.createConversation()
    })

    await act(async () => {
      await result.current.sendMessage('q', convId)
    })

    // After stream ends, partial should still hold the last value (not null)
    expect(result.current.partial).not.toBeNull()
    expect(result.current.partial?.content).toBe('final')
    expect(result.current.partial?.convId).toBe(convId)
  })

  test('subscribe 回调收到 partial 通知', async () => {
    queryStreamMock.mockImplementation(() =>
      makeStream([
        { content: 'X' },
        { content: 'Y' },
        { done: true, sources: [] },
      ]),
    )

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    const received: Array<string | null> = []
    let unsubscribe: (() => void) | null = null
    act(() => {
      unsubscribe = result.current.subscribe((p) => {
        received.push(p?.content ?? null)
      })
    })

    let convId = ''
    act(() => {
      convId = result.current.createConversation()
    })

    await act(async () => {
      await result.current.sendMessage('q', convId)
    })

    expect(received).toContain('X')
    expect(received).toContain('XY')
    // Final retained partial
    expect(received[received.length - 1]).toBe('XY')

    // Unsubscribe stops notifications
    const beforeCount = received.length
    act(() => {
      unsubscribe!()
    })
    expect(received.length).toBe(beforeCount)
  })

  test('getPartial 返回最新 partial 值（ref 同步）', async () => {
    queryStreamMock.mockImplementation(() =>
      makeStream([
        { content: 'P1' },
        { content: 'P2' },
        { done: true, sources: [] },
      ]),
    )

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let convId = ''
    act(() => {
      convId = result.current.createConversation()
    })

    // Initial: null
    expect(result.current.getPartial()).toBeNull()

    await act(async () => {
      await result.current.sendMessage('q', convId)
    })

    // After stream: getPartial() returns the retained value
    const p = result.current.getPartial()
    expect(p).not.toBeNull()
    expect(p?.content).toBe('P1P2')
  })

  test('abort() 中断流：partial 停留在中断时的内容 + lastError.kind === "aborted"', async () => {
    let resolveNext: (() => void) | null = null
    const stream = (async function* () {
      yield { content: 'partial-' } as StreamEvent
      await new Promise<void>((r) => {
        resolveNext = r
      })
      yield { content: 'after-stop' } as StreamEvent
      yield { done: true, sources: [] } as StreamEvent
    })()
    queryStreamMock.mockImplementation(() => stream)

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let convId = ''
    act(() => {
      convId = result.current.createConversation()
    })

    let sendPromise: Promise<void> = Promise.resolve()
    act(() => {
      sendPromise = result.current.sendMessage('q', convId)
    })

    // Wait for the first chunk to arrive
    await waitFor(() => {
      const conv = result.current.conversations.find((c) => c.id === convId)
      expect(conv?.messages[1]?.content).toBe('partial-')
    })

    // User clicks Stop
    act(() => {
      result.current.abort()
    })

    // Release the next chunk (will arrive but the consumer is aborted)
    await act(async () => {
      resolveNext!()
      await sendPromise
    })

    // isLoading is back to false
    expect(result.current.isLoading).toBe(false)

    // Partial content stays at 'partial-' (the 'after-stop' chunk must not be appended)
    const convAfter = result.current.conversations.find((c) => c.id === convId)!
    expect(convAfter.messages[1].content).toBe('partial-')

    // lastError reflects the abort
    expect(result.current.lastError).not.toBeNull()
    expect(result.current.lastError?.kind).toBe('aborted')
    expect(result.current.lastError?.messageId).toBe(convAfter.messages[1].id)
  })

  test('流式错误:lastError.kind === "error" 且 message content 不再被 [错误: ...] 污染', async () => {
    queryStreamMock.mockImplementation(() =>
      makeStream([
        { content: 'halfway' },
        // simulate a stream error: throw from the generator
        // (the for-await will propagate this as a real error)
      ] as Array<Partial<StreamEvent>>),
    )
    // Wrap the generator so the second yield throws
    queryStreamMock.mockImplementationOnce(async function* () {
      yield { content: 'halfway' } as StreamEvent
      throw new Error('网络中断')
    })

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let convId = ''
    act(() => {
      convId = result.current.createConversation()
    })

    await act(async () => {
      await result.current.sendMessage('q', convId)
    })

    // Partial content must NOT be polluted with "[错误: ...]"
    const conv = result.current.conversations.find((c) => c.id === convId)!
    expect(conv.messages[1].content).toBe('halfway')
    expect(conv.messages[1].content).not.toContain('[错误:')
    expect(conv.messages[1].content).not.toContain('网络中断')

    // lastError is set with kind 'error' and the error message
    expect(result.current.lastError).not.toBeNull()
    expect(result.current.lastError?.kind).toBe('error')
    expect(result.current.lastError?.message).toBe('网络中断')
    expect(result.current.lastError?.messageId).toBe(conv.messages[1].id)
  })

  test('resendLast() 重新发送当前对话的最后一条 user 消息', async () => {
    let sendCount = 0
    queryStreamMock.mockImplementation(() => {
      sendCount += 1
      return makeStream([{ content: 'reply' }, { done: true, sources: [] }])
    })

    const { result } = renderHook(() => useChatContext(), { wrapper: makeWrapper() })

    let convId = ''
    act(() => {
      convId = result.current.createConversation()
    })

    // First send
    await act(async () => {
      await result.current.sendMessage('first question', convId)
    })
    expect(sendCount).toBe(1)
    expect(result.current.conversations[0].messages).toHaveLength(2)

    // resendLast should re-send the user message
    await act(async () => {
      await result.current.resendLast()
    })
    expect(sendCount).toBe(2)

    // Now there should be 4 messages: user, assistant, user (resent), assistant (resent)
    const conv = result.current.conversations.find((c) => c.id === convId)!
    expect(conv.messages).toHaveLength(4)
    expect(conv.messages[2].role).toBe('user')
    expect(conv.messages[2].content).toBe('first question')
    expect(conv.messages[3].role).toBe('assistant')
  })
})

// =====================================================================
// 兼容性：useConversations adapter
// =====================================================================

describe('useConversations - adapter 兼容性', () => {
  test('useConversations 返回完整旧接口字段', async () => {
    const { result } = renderHook(() => useConversations(), { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(result.current.conversations).toBeDefined()
    })

    // Should expose all expected fields
    expect(result.current).toHaveProperty('conversations')
    expect(result.current).toHaveProperty('currentId')
    expect(result.current).toHaveProperty('currentConversation')
    expect(result.current).toHaveProperty('messages')
    expect(result.current).toHaveProperty('currentMessages')
    expect(result.current).toHaveProperty('createConversation')
    expect(result.current).toHaveProperty('switchConversation')
    expect(result.current).toHaveProperty('deleteConversation')
    expect(result.current).toHaveProperty('updateMessages')
    expect(result.current).toHaveProperty('renameConversation')
  })

  test('useConversations.messages === currentMessages（同源同值）', async () => {
    const { result } = renderHook(() => useConversations(), { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(result.current.conversations).toBeDefined()
    })

    // Both fields point to the same array (reference equality)
    expect(result.current.messages).toBe(result.current.currentMessages)
  })

  test('useConversations 的 CRUD actions 与 useChatContext 一致', async () => {
    const { result } = renderHook(() => useConversations(), { wrapper: makeWrapper() })

    let id = ''
    act(() => {
      id = result.current.createConversation()
    })

    expect(result.current.currentId).toBe(id)

    act(() => {
      result.current.renameConversation(id, 'Adapter 标题')
    })
    expect(result.current.conversations[0].title).toBe('Adapter 标题')

    act(() => {
      result.current.deleteConversation(id)
    })
    expect(result.current.conversations.find((c) => c.id === id)).toBeUndefined()
  })
})
