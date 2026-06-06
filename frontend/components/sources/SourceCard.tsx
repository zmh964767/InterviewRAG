'use client'

import type { SourceRef } from '@/lib/types'

interface SourceCardProps {
  source: SourceRef
}

export function SourceCard({ source }: SourceCardProps) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
        {source.category}
      </span>
      <span className="text-gray-600 truncate flex-1">
        {source.question_text.slice(0, 60)}
        {source.question_text.length > 60 ? '...' : ''}
      </span>
      <span className="text-gray-400 shrink-0">
        {(source.score * 100).toFixed(0)}%
      </span>
    </div>
  )
}
