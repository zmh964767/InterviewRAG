'use client'

import { useEffect, useState } from 'react'
import { adminGetSweep } from '@/lib/api'
import type { SweepResponse, SweepRow } from '@/lib/types'

function formatPct(n: number): string {
  return (n * 100).toFixed(1) + '%'
}

function formatDuration(s: number | null): string {
  if (s == null) return '—'
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const rest = Math.floor(s - m * 60)
  return `${m}m ${rest}s`
}

/** 提升百分比:winner 相对 latest_summary baseline 的变化率
 *  - baseline = 0 时返回 '—' (没有可比较的基准)
 *  - 正向:var(--ink); 持平:var(--ink-muted); 下降:#991b1b
 */
function formatImprovement(winnerHr5: number, baseline: number): {
  text: string
  color: string
} {
  if (baseline <= 0) {
    return { text: '—', color: 'var(--ink-muted)' }
  }
  const pct = (winnerHr5 - baseline) / baseline
  const rounded = Math.round(pct * 1000) / 10  // 一位小数
  const sign = rounded > 0 ? '+' : ''
  const text = `${sign}${rounded.toFixed(1)}%`
  if (Math.abs(pct) < 1e-6) {
    return { text: '持平', color: 'var(--ink-muted)' }
  }
  const color = pct > 0 ? 'var(--ink)' : '#991b1b'
  return { text, color }
}

export function SweepView() {
  const [data, setData] = useState<SweepResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    adminGetSweep()
      .then((d) => setData(d))
      .catch((e) => setError(e?.message || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <p className="text-sm py-8 text-center" style={{ color: 'var(--ink-muted)' }}>加载 Sweep 结果中…</p>
  }
  if (error) {
    return (
      <div className="p-4 rounded-xl" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b' }}>
        {error}
      </div>
    )
  }
  if (!data || data.rows.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-sm mb-2" style={{ color: 'var(--ink-muted)' }}>暂未运行 sweep</p>
        <p className="text-xs" style={{ color: 'var(--ink-muted)' }}>去后端运行: <code className="px-1.5 py-0.5 rounded" style={{ background: 'var(--paper)' }}>cd backend &amp;&amp; python -m evaluation.sweep</code></p>
      </div>
    )
  }

  // 按 E_hr5 降序
  const sortedRows = [...data.rows].sort((a, b) => b.E_hr5 - a.E_hr5)
  const winner = data.winner
  const baseline = data.baseline_e_hr5

  return (
    <div>
      {/* Winner 推荐区 */}
      {winner && (
        <div
          className="rounded-xl p-5 mb-6"
          style={{ background: 'var(--cream)', border: '1px solid var(--border-subtle)' }}
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base">🏆</span>
            <h2 className="text-sm font-semibold" style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>
              推荐组合
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <WinnerField label="类型" value={winner.type === 'prompt' ? 'Prompt 扫描' : 'Chunk 扫描'} />
            <WinnerField
              label="Prompt variant"
              value={winner.prompt_variant != null ? `v${winner.prompt_variant}` : '—'}
            />
            <WinnerField
              label="Chunk size"
              value={winner.chunk_size != null ? String(winner.chunk_size) : '—'}
            />
            <WinnerField
              label="E HR@5"
              value={formatPct(winner.E_hr5)}
              subValue={formatImprovement(winner.E_hr5, baseline)}
              highlight
            />
          </div>
        </div>
      )}

      {/* 组合表 */}
      <div className="rounded-xl overflow-hidden" style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}>
        <div
          className="grid items-center px-4 py-2 text-xs font-medium"
          style={{
            gridTemplateColumns: '0.7fr 0.6fr 0.6fr 0.7fr 0.7fr 0.7fr 0.7fr 0.5fr 0.4fr',
            color: 'var(--ink-muted)',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <span>类型</span>
          <span>Variant</span>
          <span>Chunk</span>
          <span>E HR@5</span>
          <span>E MRR</span>
          <span>B HR@5</span>
          <span>B MRR</span>
          <span className="text-right">耗时</span>
          <span className="text-right">标识</span>
        </div>
        {sortedRows.map((row, i) => {
          const isWinner =
            winner != null &&
            row.type === winner.type &&
            row.prompt_variant === winner.prompt_variant &&
            row.chunk_size === winner.chunk_size
          return <SweepRowItem key={`${row.type}-${row.prompt_variant ?? '-'}-${row.chunk_size ?? '-'}-${i}`} row={row} isWinner={isWinner} />
        })}
      </div>
    </div>
  )
}

function WinnerField({
  label,
  value,
  subValue,
  highlight,
}: {
  label: string
  value: string
  subValue?: { text: string; color: string }
  highlight?: boolean
}) {
  return (
    <div>
      <div className="text-xs mb-1" style={{ color: 'var(--ink-muted)' }}>{label}</div>
      <div
        className="text-sm font-medium tabular-nums"
        style={{
          color: highlight ? 'var(--ink)' : 'var(--ink)',
          fontFamily: 'var(--font-display)',
        }}
      >
        {value}
      </div>
      {subValue && (
        <div
          className="text-xs mt-0.5 tabular-nums"
          style={{ color: subValue.color }}
        >
          提升 {subValue.text}
        </div>
      )}
    </div>
  )
}

function SweepRowItem({ row, isWinner }: { row: SweepRow; isWinner: boolean }) {
  return (
    <div
      className="grid items-center px-4 py-2.5 text-sm"
      style={{
        gridTemplateColumns: '0.7fr 0.6fr 0.6fr 0.7fr 0.7fr 0.7fr 0.7fr 0.5fr 0.4fr',
        borderBottom: '1px solid var(--border-subtle)',
        background: isWinner ? 'var(--cream)' : 'transparent',
        fontWeight: isWinner ? 500 : 400,
      }}
    >
      <span style={{ color: 'var(--ink-muted)' }}>{row.type === 'prompt' ? 'Prompt' : 'Chunk'}</span>
      <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>
        {row.prompt_variant != null ? `v${row.prompt_variant}` : '—'}
      </span>
      <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>
        {row.chunk_size != null ? row.chunk_size : '—'}
      </span>
      <span className="tabular-nums" style={{ color: 'var(--ink)' }}>{formatPct(row.E_hr5)}</span>
      <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>{formatPct(row.E_mrr)}</span>
      <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>{formatPct(row.B_hr5)}</span>
      <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>{formatPct(row.B_mrr)}</span>
      <span className="tabular-nums text-right" style={{ color: 'var(--ink-muted)' }}>{formatDuration(row.duration_s)}</span>
      <span className="text-right text-base" style={{ color: isWinner ? 'var(--ink)' : 'transparent' }}>
        ⭐
      </span>
    </div>
  )
}
