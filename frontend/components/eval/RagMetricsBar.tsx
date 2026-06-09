'use client'

import type { EvalMetrics } from '@/lib/types'

interface RagMetricsBarProps {
  metrics: EvalMetrics
  compact?: boolean
}

const LABELS: Record<keyof EvalMetrics, string> = {
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer Relevancy',
  context_precision: 'Context Precision',
  context_recall: 'Context Recall',
}

const KEYS: (keyof EvalMetrics)[] = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']

export function RagMetricsBar({ metrics, compact = false }: RagMetricsBarProps) {
  const pct = (v: number) => (v * 100).toFixed(1) + '%'
  return (
    <div className={compact ? 'space-y-2' : 'space-y-3'}>
      {KEYS.map((key) => {
        const val = metrics[key]
        return (
          <div key={key}>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs" style={{ color: 'var(--ink-light)' }}>{LABELS[key]}</span>
              <span
                className={`${compact ? 'text-xs' : 'text-sm'} font-medium tabular-nums`}
                style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}
              >
                {pct(val)}
              </span>
            </div>
            {!compact && (
              <div className="w-full h-1.5 rounded-full" style={{ background: 'var(--cream)' }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${val * 100}%`, background: 'var(--ink)' }}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
