'use client'

import { useEffect, useState, useRef } from 'react'
import { adminCompareEval } from '@/lib/api'
import type { CompareResponse, EvalSummaryItem, MetricDiff } from '@/lib/types'

interface Props {
  /** 历史快照列表(最新在前) */
  history: EvalSummaryItem[]
  /** 最新快照(用 'latest' 关键字作为选项) */
  latest: EvalSummaryItem | null
}

const METRIC_LABELS: Record<MetricDiff['name'], string> = {
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer Relevancy',
  context_precision: 'Context Precision',
  context_recall: 'Context Recall',
}

function formatTs(ts: string): string {
  if (!ts) return ''
  const normalized = ts.replace(/T(\d{2})-(\d{2})-(\d{2})/, 'T$1:$2:$3')
  const d = new Date(normalized)
  return isNaN(d.getTime()) ? ts : d.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
}

function formatPct(n: number): string {
  return (n * 100).toFixed(1) + '%'
}

function formatChange(change: number): string {
  const sign = change > 0 ? '+' : ''
  return `${sign}${change.toFixed(3)}`
}

export function EvalCompareView({ history, latest }: Props) {
  // 选项 = [latest, ...history] (latest 在前)
  const options: { value: string; label: string; disabled?: boolean }[] = []
  if (latest) {
    options.push({ value: 'latest', label: `最新 (${formatTs(latest.timestamp)})` })
  } else {
    options.push({ value: 'latest', label: '最新', disabled: true })
  }
  for (const h of history) {
    options.push({ value: h.timestamp, label: formatTs(h.timestamp) })
  }

  // 默认:base = 较早(选倒数第 2 个,history 是最新在前),target = latest
  const defaultTarget = 'latest'
  const defaultBase = options.length >= 2
    ? options[options.length - 1].value
    : 'latest'

  const [base, setBase] = useState<string>(defaultBase)
  const [target, setTarget] = useState<string>(defaultTarget)
  const [data, setData] = useState<CompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!base || !target) return
    if (base === target) {
      setData(null)
      setError(null)
      return
    }
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    setLoading(true)
    setError(null)
    adminCompareEval(base, target, ac.signal)
      .then((d) => setData(d))
      .catch((e) => {
        if (e?.name !== 'AbortError') setError(e?.message || '对比失败')
      })
      .finally(() => {
        if (abortRef.current === ac) abortRef.current = null
        setLoading(false)
      })
    return () => ac.abort()
  }, [base, target])

  return (
    <div>
      {/* 顶部:base/target 选择器 */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-muted)' }}>
          <span>Base</span>
          <select
            value={base}
            onChange={(e) => setBase(e.target.value)}
            className="rounded-md px-2 py-1 text-sm"
            style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          >
            {options.map((o) => (
              <option key={`b-${o.value}`} value={o.value} disabled={o.disabled}>{o.label}</option>
            ))}
          </select>
        </label>
        <span style={{ color: 'var(--ink-muted)' }}>→</span>
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-muted)' }}>
          <span>Target</span>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="rounded-md px-2 py-1 text-sm"
            style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          >
            {options.map((o) => (
              <option key={`t-${o.value}`} value={o.value} disabled={o.disabled}>{o.label}</option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <div className="p-4 rounded-xl mb-4" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b' }}>
          {error}
        </div>
      )}

      {loading && !data && (
        <p className="text-sm py-8 text-center" style={{ color: 'var(--ink-muted)' }}>加载对比中…</p>
      )}

      {base === target && (
        <p className="text-sm py-8 text-center" style={{ color: 'var(--ink-muted)' }}>两次快照相同</p>
      )}

      {data && (
        <>
          {/* 顶部统计徽章 */}
          <div className="flex gap-3 mb-5">
            <StatBadge label="提升" value={data.improved} color="var(--ink)" />
            <StatBadge label="持平" value={data.same} color="var(--ink-muted)" />
            <StatBadge label="下降" value={data.regressed} color="#991b1b" />
          </div>

          {/* 指标对比表 */}
          <div className="rounded-xl overflow-hidden" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
            <div
              className="grid items-center px-4 py-2 text-xs font-medium"
              style={{
                gridTemplateColumns: '1.4fr 1fr 1fr 1fr 0.6fr',
                color: 'var(--ink-muted)',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <span>指标</span>
              <span>Base</span>
              <span>Target</span>
              <span>变化</span>
              <span className="text-right">方向</span>
            </div>
            {data.diffs.map((d) => (
              <DiffRow key={d.name} diff={d} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-xl px-4 py-2" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
      <span className="text-xs mr-1.5" style={{ color: 'var(--ink-muted)' }}>{label}</span>
      <span className="text-sm font-semibold tabular-nums" style={{ color, fontFamily: 'var(--font-display)' }}>{value}</span>
    </div>
  )
}

function DiffRow({ diff }: { diff: MetricDiff }) {
  const dirColor =
    diff.direction === 'up' ? 'var(--ink)' :
    diff.direction === 'down' ? '#991b1b' :
    'var(--ink-muted)'
  const arrow =
    diff.direction === 'up' ? '↑' :
    diff.direction === 'down' ? '↓' :
    '→'
  return (
    <div
      className="grid items-center px-4 py-3 text-sm"
      style={{
        gridTemplateColumns: '1.4fr 1fr 1fr 1fr 0.6fr',
        borderBottom: '1px solid var(--border-subtle)',
      }}
    >
      <span style={{ color: 'var(--ink)' }}>{METRIC_LABELS[diff.name]}</span>
      <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>{formatPct(diff.base)}</span>
      <span className="tabular-nums font-medium" style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>{formatPct(diff.target)}</span>
      <span className="tabular-nums" style={{ color: dirColor }}>{formatChange(diff.change)}</span>
      <span className="text-right text-base" style={{ color: dirColor }}>{arrow}</span>
    </div>
  )
}
