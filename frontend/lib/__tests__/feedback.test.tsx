import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { submitFeedback, adminGetFeedback, adminGetFeedbackStats } from '@/lib/api'
import { FeedbackView } from '@/components/eval/FeedbackView'

describe('submitFeedback', () => {
  it('sends POST to /api/feedback with body and Content-Type', async () => {
    const mockResponse = { id: 'fb-1', message_id: 'm-1' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await submitFeedback({
      message_id: 'm-1',
      conversation_id: 'c-1',
      rating: 1,
      comment: null,
      message_content: 'hello',
      message_role: 'assistant',
    })

    expect(result).toEqual(mockResponse)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/feedback$/)
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    const body = JSON.parse(init.body)
    expect(body).toEqual({
      message_id: 'm-1',
      conversation_id: 'c-1',
      rating: 1,
      comment: null,
      message_content: 'hello',
      message_role: 'assistant',
    })
  })

  it('throws with detail on non-OK response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'invalid rating' }),
    }))

    await expect(submitFeedback({
      message_id: 'm',
      conversation_id: 'c',
      rating: 1,
      comment: null,
      message_content: 'x',
      message_role: 'assistant',
    })).rejects.toThrow('invalid rating')
  })
})

describe('adminGetFeedback', () => {
  it('passes query params correctly', async () => {
    const mockResponse = { items: [], total: 0, page: 2, size: 10 }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await adminGetFeedback({ rating: -1, since: '2026-06-01 00:00:00', page: 2, size: 10 })

    expect(result).toEqual(mockResponse)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/admin/feedback')
    expect(url).toContain('rating=-1')
    expect(url).toContain('since=2026-06-01+00%3A00%3A00')
    expect(url).toContain('page=2')
    expect(url).toContain('size=10')
    expect(init.credentials).toBe('include')
  })

  it('omits undefined params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, size: 50 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await adminGetFeedback({})

    const [url] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/admin\/feedback$/)
  })
})

describe('adminGetFeedbackStats', () => {
  it('appends since param when provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ positive: 1, negative: 0, total: 1, rate: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await adminGetFeedbackStats('2026-06-01 00:00:00')

    const [url] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/admin/feedback/stats')
    expect(url).toContain('since=')
  })
})

describe('FeedbackView', () => {

  it('renders 3 stat badges with values from stats', async () => {
    const mockStats = { positive: 3, negative: 2, total: 5, rate: 0.4 }
    const mockList = { items: [], total: 5, page: 1, size: 20 }

    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/stats')) {
        return { ok: true, json: async () => mockStats }
      }
      return { ok: true, json: async () => mockList }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<FeedbackView />)

    await waitFor(() => {
      // 3 个 stat badge 数字:3 / 2 / 40.0%(rate * 100)
      expect(screen.getByText('3')).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
      expect(screen.getByText('40.0%')).toBeInTheDocument()
    })
  })
})
