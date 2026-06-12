'use client'

import { useState } from 'react'
import type { EvalItemResult } from '@/lib/types'

interface EvalItemRowProps {
  item: EvalItemResult
  index: number
}

function formatMetric(v: number | undefined): string {
  if (v === undefined) return '—'
  return (v * 100).toFixed(1) + '%'
}

function getMetricColor(v: number | undefined): string {
  if (v === undefined) return 'var(--ink-muted)'
  if (v >= 0.8) return 'var(--success)'
  if (v >= 0.5) return 'var(--ink-muted)'
  return 'var(--accent)'
}

export function EvalItemRow({ item, index }: EvalItemRowProps) {
  const [expanded, setExpanded] = useState(false)
  const faithfulness = item.metrics.faithfulness
  return (
    <div style={{ borderTop: '1px solid var(--border-subtle)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-4 text-left hover:bg-var-cream"
        style={{ background: expanded ? 'var(--cream)' : 'transparent' }}
      >
        <span className="text-xs tabular-nums w-6" style={{ color: 'var(--ink-muted)' }}>#{index + 1}</span>
        <span className="flex-1 text-sm truncate" style={{ color: 'var(--ink-light)' }}>
          {item.question || '(无题面)'}
        </span>
        <span className="text-xs tabular-nums px-1.5 py-0.5 rounded" style={{ color: getMetricColor(faithfulness), border: '1px solid var(--border-subtle)' }}>
          F {formatMetric(faithfulness)}
        </span>
        <span className="text-xs tabular-nums px-1.5 py-0.5 rounded" style={{ color: getMetricColor(item.metrics.answer_relevancy), border: '1px solid var(--border-subtle)' }}>
          R {formatMetric(item.metrics.answer_relevancy)}
        </span>
        <svg className="w-3 h-3 transition-transform" style={{ color: 'var(--ink-muted)', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="px-4 pb-4 space-y-3" style={{ background: 'var(--cream)' }}>
          {item.error && (
            <div className="p-2 rounded text-xs" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b' }}>
              评估失败: {item.error}
            </div>
          )}
          <div>
            <p className="text-xs font-medium mb-1" style={{ color: 'var(--ink-muted)' }}>指标</p>
            <div className="grid grid-cols-4 gap-2 text-xs">
              {Object.entries(item.metrics).map(([k, v]) => (
                <div key={k} className="px-2 py-1.5 rounded" style={{ background: 'var(--paper)' }}>
                  <div className="font-mono" style={{ color: 'var(--ink-muted)' }}>{k}</div>
                  <div className="text-sm tabular-nums" style={{ color: getMetricColor(v) }}>{formatMetric(v)}</div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-medium mb-1" style={{ color: 'var(--ink-muted)' }}>题面</p>
            <div className="text-sm whitespace-pre-wrap leading-relaxed p-2 rounded" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
              {item.question || '(无)'}
            </div>
          </div>
          <div>
            <p className="text-xs font-medium mb-1" style={{ color: 'var(--ink-muted)' }}>生成的答案</p>
            <div className="text-sm whitespace-pre-wrap leading-relaxed p-2 rounded" style={{ background: 'var(--paper)', color: 'var(--ink-light)' }}>
              {item.answer || '(无)'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
