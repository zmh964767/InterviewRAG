/**
 * useIngestTask 单元测试
 *
 * 覆盖场景：
 * - start 触发轮询 + 立即拉一次
 * - 终端状态(done/failed)自动停止轮询
 * - 404 错误提示任务丢失
 * - 其他错误提示
 * - unmount 时清理 interval
 * - stop 手动停止
 */

import { describe, test, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useIngestTask } from '@/hooks/useIngestTask'
import type { TaskStatusResponse } from '@/lib/types'

// ---------- Mock api ----------

const adminGetTaskStatusMock = vi.fn()

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    adminGetTaskStatus: (...args: unknown[]) => adminGetTaskStatusMock(...args),
  }
})

function makeTaskStatus(overrides: Partial<TaskStatusResponse> = {}): TaskStatusResponse {
  return {
    task_id: 't1',
    status: 'running',
    source_type: 'md',
    source: 'test.md',
    total: 10,
    done: 5,
    ingested: 5,
    duplicates: 0,
    errors: 0,
    started_at: '2025-01-01T00:00:00',
    finished_at: null,
    error_message: null,
    ...overrides,
  }
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  adminGetTaskStatusMock.mockReset()
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

// ---------- Tests ----------

describe('useIngestTask', () => {
  test('初始状态：非轮询、无 task', () => {
    const { result } = renderHook(() => useIngestTask())
    expect(result.current.isPolling).toBe(false)
    expect(result.current.task).toBeNull()
    expect(result.current.isTerminal).toBe(false)
    expect(result.current.error).toBeNull()
  })

  test('start 触发轮询，立即拉一次', async () => {
    adminGetTaskStatusMock.mockResolvedValue(makeTaskStatus())
    const { result } = renderHook(() => useIngestTask())

    act(() => { result.current.start('t1') })

    expect(result.current.isPolling).toBe(true)
    expect(adminGetTaskStatusMock).toHaveBeenCalledTimes(1)
    expect(adminGetTaskStatusMock).toHaveBeenCalledWith('t1')
  })

  test('done 状态自动停止轮询', async () => {
    adminGetTaskStatusMock.mockResolvedValue(makeTaskStatus({ status: 'done' }))
    const { result } = renderHook(() => useIngestTask())

    act(() => { result.current.start('t1') })

    await waitFor(() => {
      expect(result.current.isPolling).toBe(false)
      expect(result.current.isTerminal).toBe(true)
    })
  })

  test('failed 状态自动停止轮询', async () => {
    adminGetTaskStatusMock.mockResolvedValue(makeTaskStatus({ status: 'failed', error_message: 'boom' }))
    const { result } = renderHook(() => useIngestTask())

    act(() => { result.current.start('t1') })

    await waitFor(() => {
      expect(result.current.isPolling).toBe(false)
      expect(result.current.isTerminal).toBe(true)
    })
  })

  test('404 错误设置任务丢失提示', async () => {
    adminGetTaskStatusMock.mockRejectedValue(new Error('HTTP 404'))
    const { result } = renderHook(() => useIngestTask())

    act(() => { result.current.start('t1') })

    await waitFor(() => {
      expect(result.current.error).toBe('任务已丢失（可能服务重启）')
      expect(result.current.isPolling).toBe(false)
    })
  })

  test('其他错误设置通用提示', async () => {
    adminGetTaskStatusMock.mockRejectedValue(new Error('network down'))
    const { result } = renderHook(() => useIngestTask())

    act(() => { result.current.start('t1') })

    await waitFor(() => {
      expect(result.current.error).toBe('network down')
      expect(result.current.isPolling).toBe(false)
    })
  })

  test('stop 手动停止轮询', async () => {
    adminGetTaskStatusMock.mockResolvedValue(makeTaskStatus())
    const { result } = renderHook(() => useIngestTask())

    act(() => { result.current.start('t1') })
    expect(result.current.isPolling).toBe(true)

    act(() => { result.current.stop() })
    expect(result.current.isPolling).toBe(false)
  })

  test('unmount 时清理 interval', async () => {
    adminGetTaskStatusMock.mockResolvedValue(makeTaskStatus())
    const { result, unmount } = renderHook(() => useIngestTask())

    act(() => { result.current.start('t1') })
    unmount()

    // 推进时间不应再触发调用
    const callCount = adminGetTaskStatusMock.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(adminGetTaskStatusMock).toHaveBeenCalledTimes(callCount)
  })
})
