'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { adminGetFeedback, adminGetFeedbackStats } from '@/lib/api'
import type { FeedbackItem, FeedbackStats } from '@/lib/types'
import { EVAL } from '@/lib/copy'

type RatingFilter = 'all' | '1' | '-1'
type TimeFilter = 'all' | 'today' | 'week'

function formatPct(n: number): string {
  return (n * 100).toFixed(1) + '%'
}

function formatTs(ts: string): string {
  const d = new Date(ts.replace(' ', 'T'))
  return isNaN(d.getTime()) ? ts : d.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n) + '…'
}

function sinceForFilter(t: TimeFilter): string | undefined {
  if (t === 'all') return undefined
  const d = new Date()
  if (t === 'today') d.setHours(0, 0, 0, 0)
  else if (t === 'week') d.setDate(d.getDate() - 7)
  return d.toISOString().slice(0, 19).replace('T', ' ')
}

export function FeedbackView() {
  const [items, setItems] = useState<FeedbackItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [stats, setStats] = useState<FeedbackStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [ratingFilter, setRatingFilter] = useState<RatingFilter>('all')
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('all')
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(async (p: number) => {
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    setLoading(true)
    setError(null)
    try {
      const since = sinceForFilter(timeFilter)
      const rating = ratingFilter === 'all' ? undefined : (Number(ratingFilter) as 1 | -1)
      const [list, s] = await Promise.all([
        adminGetFeedback({ rating, since, page: p, size }),
        adminGetFeedbackStats(since),
      ])
      if (ac.signal.aborted) return
      setItems(list.items)
      setTotal(list.total)
      setPage(list.page)
      setStats(s)
    } catch (e) {
      if ((e as { name?: string })?.name !== 'AbortError') {
        setError((e as Error).message || '加载失败')
      }
    } finally {
      if (abortRef.current === ac) abortRef.current = null
      setLoading(false)
    }
  }, [ratingFilter, timeFilter, size])

  useEffect(() => {
    void load(1)
    return () => abortRef.current?.abort()
  }, [load])

  const totalPages = Math.max(1, Math.ceil(total / size))

  return (
    <div>
      <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>
        {EVAL.FEEDBACK_TITLE}
      </h2>

      {/* 统计徽章 */}
      {stats && (
        <div className="flex gap-3 mb-5">
          <StatBadge label={EVAL.FEEDBACK_STATS_POSITIVE} value={stats.positive} color="var(--ink)" />
          <StatBadge label={EVAL.FEEDBACK_STATS_NEGATIVE} value={stats.negative} color="#991b1b" />
          <StatBadge
            label={EVAL.FEEDBACK_STATS_RATE}
            value={stats.total > 0 ? formatPct(stats.rate) : '—'}
            color="var(--ink-muted)"
          />
        </div>
      )}

      {/* 筛选条 */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-muted)' }}>
          <span>评分</span>
          <select
            value={ratingFilter}
            onChange={(e) => setRatingFilter(e.target.value as RatingFilter)}
            className="rounded-md px-2 py-1 text-sm"
            style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          >
            <option value="all">{EVAL.FEEDBACK_FILTER_ALL}</option>
            <option value="1">{EVAL.FEEDBACK_RATING_POSITIVE}</option>
            <option value="-1">{EVAL.FEEDBACK_RATING_NEGATIVE}</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-muted)' }}>
          <span>时间</span>
          <select
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value as TimeFilter)}
            className="rounded-md px-2 py-1 text-sm"
            style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          >
            <option value="all">{EVAL.FEEDBACK_FILTER_ALL}</option>
            <option value="today">{EVAL.FEEDBACK_FILTER_TODAY}</option>
            <option value="week">{EVAL.FEEDBACK_FILTER_WEEK}</option>
          </select>
        </label>
        <span className="text-xs ml-auto" style={{ color: 'var(--ink-muted)' }}>
          共 {total} 条 · 第 {page}/{totalPages} 页
        </span>
      </div>

      {error && (
        <div className="p-4 rounded-xl mb-4" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b' }}>
          {error}
        </div>
      )}

      {/* 列表 */}
      {loading && items.length === 0 ? (
        <p className="text-sm py-8 text-center" style={{ color: 'var(--ink-muted)' }}>加载中…</p>
      ) : items.length === 0 ? (
        <p className="text-sm py-8 text-center" style={{ color: 'var(--ink-muted)' }}>暂无反馈</p>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
          {items.map((item) => (
            <FeedbackRow key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center gap-2 mt-4">
          <button
            onClick={() => void load(page - 1)}
            disabled={page <= 1 || loading}
            className="px-3 py-1 rounded text-sm"
            style={{
              background: 'var(--paper)',
              border: '1px solid var(--border)',
              color: page <= 1 ? 'var(--ink-muted)' : 'var(--ink)',
              opacity: page <= 1 ? 0.5 : 1,
            }}
          >
            上一页
          </button>
          <button
            onClick={() => void load(page + 1)}
            disabled={page >= totalPages || loading}
            className="px-3 py-1 rounded text-sm"
            style={{
              background: 'var(--paper)',
              border: '1px solid var(--border)',
              color: page >= totalPages ? 'var(--ink-muted)' : 'var(--ink)',
              opacity: page >= totalPages ? 0.5 : 1,
            }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}

function StatBadge({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className="rounded-xl px-4 py-2" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
      <span className="text-xs mr-1.5" style={{ color: 'var(--ink-muted)' }}>{label}</span>
      <span className="text-sm font-semibold tabular-nums" style={{ color, fontFamily: 'var(--font-display)' }}>{value}</span>
    </div>
  )
}

function FeedbackRow({ item }: { item: FeedbackItem }) {
  const isPositive = item.rating === 1
  return (
    <div className="px-4 py-3 text-sm" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <div className="flex items-center gap-3 mb-1.5">
        <span
          className="rounded px-1.5 py-0.5 text-xs font-medium"
          style={{
            background: isPositive ? 'var(--nav-active-bg)' : '#fef2f2',
            color: isPositive ? 'var(--ink)' : '#991b1b',
          }}
        >
          {isPositive ? '👍 赞' : '👎 踩'}
        </span>
        <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>{formatTs(item.created_at)}</span>
        <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>msg {truncate(item.message_id, 16)}</span>
        {item.client_ip && (
          <span className="text-xs ml-auto" style={{ color: 'var(--ink-muted)' }}>IP {item.client_ip}</span>
        )}
      </div>
      <div className="text-sm mb-1" style={{ color: 'var(--ink)' }}>{truncate(item.message_content, 100)}</div>
      {item.comment && (
        <div
          className="text-xs px-2 py-1 rounded mt-1"
          style={{ background: 'var(--nav-active-bg)', color: 'var(--ink-muted)' }}
        >
          💬 {item.comment}
        </div>
      )}
    </div>
  )
}
