'use client'

import type { Question } from '@/lib/types'
import { formatTime } from '@/lib/utils'

interface QuestionCardProps {
  question: Question
  onSelect: (q: Question) => void
  onDelete?: (q: Question) => void
}

export function QuestionCard({ question, onSelect, onDelete }: QuestionCardProps) {
  return (
    <div
      className="rounded-xl p-4 mb-3"
      style={{ background: 'var(--paper)', border: '1px solid var(--border-subtle)' }}
      onClick={() => onSelect(question)}
    >
      <div className="flex items-center gap-2 mb-2 text-xs" style={{ color: 'var(--ink-muted)' }}>
        <span className="font-mono">{question.id.slice(0, 8)}</span>
        <span>·</span>
        <span>{question.category}</span>
        <span>·</span>
        <span>{question.difficulty}</span>
        <span>·</span>
        <span>{formatTime(question.created_at)}</span>
      </div>
      <div className="text-sm mb-2" style={{ color: 'var(--ink-light)' }}>
        {question.question}
      </div>
      <div className="text-xs line-clamp-2" style={{ color: 'var(--ink-muted)' }}>
        {question.answer}
      </div>
      {onDelete && (
        <div className="flex justify-end mt-2">
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(question) }}
            className="text-xs px-3 py-1 rounded transition-colors"
            style={{ color: 'var(--accent)', border: '1px solid var(--accent)' }}
          >
            删除
          </button>
        </div>
      )}
    </div>
  )
}
