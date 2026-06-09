'use client'

import type { EvalComparisonPlan } from '@/lib/types'

interface ComparisonTableProps {
  comparison: Record<string, EvalComparisonPlan>
  compact?: boolean
}

export function ComparisonTable({ comparison, compact = false }: ComparisonTableProps) {
  const pct = (v: number) => (v * 100).toFixed(1) + '%'
  return (
    <table className={`w-full ${compact ? 'text-xs' : 'text-sm'}`}>
      <thead>
        <tr style={{ color: 'var(--ink-muted)' }}>
          <th className={`text-left ${compact ? '' : 'text-xs'} font-medium ${compact ? 'pb-1' : 'pb-2'}`}>策略</th>
          <th className={`text-right ${compact ? '' : 'text-xs'} font-medium ${compact ? 'pb-1' : 'pb-2'}`}>Hit Rate@5</th>
          <th className={`text-right ${compact ? '' : 'text-xs'} font-medium ${compact ? 'pb-1' : 'pb-2'}`}>MRR</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(comparison).map(([plan, vals]) => (
          <tr key={plan} style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <td className={compact ? 'py-1' : 'py-2 text-xs'} style={{ color: 'var(--ink-light)' }}>{plan}</td>
            <td
              className={`${compact ? 'py-1' : 'py-2 text-xs'} text-right tabular-nums`}
              style={{ color: compact ? undefined : 'var(--ink)', fontFamily: 'var(--font-display)' }}
            >
              {pct(vals['hit_rate@5'])}
            </td>
            <td
              className={`${compact ? 'py-1' : 'py-2 text-xs'} text-right tabular-nums`}
              style={{ color: compact ? undefined : 'var(--ink)', fontFamily: 'var(--font-display)' }}
            >
              {pct(vals.mrr)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
