'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/contexts/AdminAuthContext'
import type { StatsResponse, EvalSummaryResponse } from '@/lib/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

export default function AdminDashboard() {
  const { token } = useAdminAuth()
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [evalSummary, setEvalSummary] = useState<EvalSummaryResponse | null>(null)

  useEffect(() => {
    if (!token) return
    const headers = { Authorization: `Bearer ${token}` }

    fetch(`${API_BASE}/api/admin/stats`, { headers })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d && typeof d === 'object') setStats(d) })
      .catch(() => {})

    fetch(`${API_BASE}/api/admin/eval/summary`, { headers })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d && typeof d === 'object') setEvalSummary(d) })
      .catch(() => {})
  }, [token])

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-8" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
        仪表盘
      </h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="p-6 rounded-xl" style={{ background: 'var(--paper)', border: '1px solid var(--border)' }}>
          <div className="text-3xl font-light mb-1" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
            {stats?.total_questions ?? '—'}
          </div>
          <div className="text-sm" style={{ color: 'var(--ink-muted)' }}>题目总数</div>
        </div>
        <div className="p-6 rounded-xl" style={{ background: 'var(--paper)', border: '1px solid var(--border)' }}>
          <div className="text-3xl font-light mb-1" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
            {stats?.categories ? Object.keys(stats.categories).length : '—'}
          </div>
          <div className="text-sm" style={{ color: 'var(--ink-muted)' }}>分类数</div>
        </div>
        <div className="p-6 rounded-xl" style={{ background: 'var(--paper)', border: '1px solid var(--border)' }}>
          <div className="text-3xl font-light mb-1" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
            {evalSummary?.latest
              ? `${(evalSummary.latest.metrics.answer_relevancy * 100).toFixed(1)}%`
              : '—'}
          </div>
          <div className="text-sm" style={{ color: 'var(--ink-muted)' }}>最近评估 Answer Relevancy</div>
        </div>
      </div>

      {/* Category Breakdown */}
      {stats?.categories && (
        <div className="p-6 rounded-xl" style={{ background: 'var(--paper)', border: '1px solid var(--border)' }}>
          <h2 className="text-base font-semibold mb-4" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
            分类统计
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {Object.entries(stats.categories).map(([cat, count]) => (
              <div key={cat} className="flex items-center justify-between px-4 py-3 rounded-lg" style={{ background: 'var(--cream)' }}>
                <span className="text-sm" style={{ color: 'var(--ink-light)' }}>{cat}</span>
                <span className="text-sm font-medium tabular-nums" style={{ color: 'var(--ink)' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
