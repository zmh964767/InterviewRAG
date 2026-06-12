'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAdminAuth } from '@/contexts/AdminAuthContext'
import { adminGetStats, adminGetEvalSummary } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorBanner } from '@/components/ui/ErrorBanner'
import { ADMIN, STATE } from '@/lib/copy'
import type { StatsResponse, EvalSummaryResponse } from '@/lib/types'

export default function AdminDashboard() {
  const { token } = useAdminAuth()
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [evalSummary, setEvalSummary] = useState<EvalSummaryResponse | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [evalLoading, setEvalLoading] = useState(true)
  const [evalError, setEvalError] = useState<string | null>(null)

  const loadStats = useCallback(
    async (signal?: AbortSignal) => {
      setStatsLoading(true)
      setStatsError(null)
      try {
        const data = await adminGetStats(signal)
        if (signal?.aborted) return
        setStats(data)
      } catch (err) {
        if (signal?.aborted) return
        setStatsError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) setStatsLoading(false)
      }
    },
    [],
  )

  const loadEvalSummary = useCallback(
    async (signal?: AbortSignal) => {
      setEvalLoading(true)
      setEvalError(null)
      try {
        const data = await adminGetEvalSummary(signal)
        if (signal?.aborted) return
        setEvalSummary(data)
      } catch (err) {
        if (signal?.aborted) return
        setEvalError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) setEvalLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    loadStats(controller.signal)
    loadEvalSummary(controller.signal)
    return () => controller.abort()
  }, [token, loadStats, loadEvalSummary])

  // 渲染单张统计卡:加载/错误/无数据/有数据
  const renderStatValue = (
    loading: boolean,
    error: string | null,
    hasValue: boolean,
    value: React.ReactNode,
  ) => {
    if (loading) {
      return (
        <div className="flex flex-col gap-1">
          <Skeleton className="h-9 w-20" />
          <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
            {STATE.LOADING}
          </span>
        </div>
      )
    }
    if (error) {
      return <ErrorBanner message={error} variant="inline" />
    }
    if (!hasValue) {
      return (
        <div className="text-3xl font-light" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink-muted)' }}>
          —
        </div>
      )
    }
    return (
      <div className="text-3xl font-light mb-1" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
        {value}
      </div>
    )
  }

  // 分类卡 border: 错误时变红
  const cardStyle = (hasError: boolean): React.CSSProperties => ({
    background: 'var(--paper)',
    border: `1px solid ${hasError ? 'var(--accent)' : 'var(--border)'}`,
  })

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-8" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
        仪表盘
      </h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="p-6 rounded-xl" style={cardStyle(!!statsError)}>
          {renderStatValue(
            statsLoading,
            statsError,
            stats !== null,
            stats?.total_questions,
          )}
          <div className="text-sm mt-2" style={{ color: 'var(--ink-muted)' }}>
            {ADMIN.STATS.TOTAL_QUESTIONS}
          </div>
        </div>
        <div className="p-6 rounded-xl" style={cardStyle(!!statsError)}>
          {renderStatValue(
            statsLoading,
            statsError,
            stats !== null,
            stats?.categories ? Object.keys(stats.categories).length : null,
          )}
          <div className="text-sm mt-2" style={{ color: 'var(--ink-muted)' }}>
            {ADMIN.STATS.CATEGORY_COUNT}
          </div>
        </div>
        <div className="p-6 rounded-xl" style={cardStyle(!!evalError)}>
          {renderStatValue(
            evalLoading,
            evalError,
            evalSummary !== null,
            evalSummary?.latest
              ? `${(evalSummary.latest.metrics.answer_relevancy * 100).toFixed(1)}%`
              : null,
          )}
          <div className="text-sm mt-2" style={{ color: 'var(--ink-muted)' }}>
            {ADMIN.STATS.LATEST_RELEVANCY}
          </div>
        </div>
      </div>

      {/* Category Breakdown */}
      <div className="p-6 rounded-xl" style={cardStyle(!!statsError)}>
        <h2 className="text-base font-semibold mb-4" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
          {ADMIN.CATEGORIES_TITLE}
        </h2>
        {statsLoading ? (
          <div className="space-y-2" role="status" aria-label={STATE.LOADING}>
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : statsError ? (
          <ErrorBanner message={statsError} onRetry={() => loadStats()} />
        ) : !stats?.categories || Object.keys(stats.categories).length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
            {ADMIN.EMPTY_CATEGORIES}
          </p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {Object.entries(stats.categories).map(([cat, count]) => (
              <div key={cat} className="flex items-center justify-between px-4 py-3 rounded-lg" style={{ background: 'var(--cream)' }}>
                <span className="text-sm" style={{ color: 'var(--ink-light)' }}>{cat}</span>
                <span className="text-sm font-medium tabular-nums" style={{ color: 'var(--ink)' }}>{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
