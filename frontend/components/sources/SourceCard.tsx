'use client'

import { useState } from 'react'
import type { SourceRef } from '@/lib/types'

interface SourceCardProps {
  source: SourceRef
  index: number
}

export function SourceCard({ source, index }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false)
  const scorePercent = Math.round(source.score * 100)

  return (
    <div
      className="rounded-lg overflow-hidden transition-all"
      style={{ background: 'var(--cream)', border: '1px solid var(--border-subtle)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'var(--paper)' }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className="text-[10px] font-medium shrink-0"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--ink-muted)' }}
          >
            #{index + 1}
          </span>
          <span
            className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium shrink-0"
            style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}
          >
            {source.category}
          </span>
          <span className="text-xs truncate" style={{ color: 'var(--ink-light)' }}>
            {source.question_text}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          {/* Score - only show when reranker is active (scores > 10%) */}
          {scorePercent > 10 && (
            <>
              <div className="w-10 h-1 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${scorePercent}%`,
                    background: scorePercent >= 70 ? 'var(--success)' : scorePercent >= 50 ? 'var(--warning)' : 'var(--ink-muted)',
                  }}
                />
              </div>
              <span
                className="text-[10px] tabular-nums w-7 text-right"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--ink-muted)' }}
              >
                {scorePercent}%
              </span>
            </>
          )}
          <svg
            className="w-3 h-3 transition-transform"
            style={{ color: 'var(--ink-muted)', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t animate-fade-in" style={{ borderColor: 'var(--border-subtle)' }}>
          {source.answer_text ? (
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--ink-light)' }}>
              {source.answer_text}
            </p>
          ) : (
            <p className="text-xs italic" style={{ color: 'var(--ink-muted)' }}>
              暂无参考答案
            </p>
          )}
        </div>
      )}
    </div>
  )
}
