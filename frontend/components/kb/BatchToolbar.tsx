'use client'

import { KB } from '@/lib/copy'

interface BatchToolbarProps {
  selectedCount: number
  onDelete: () => void
}

export function BatchToolbar({ selectedCount, onDelete }: BatchToolbarProps) {
  if (selectedCount === 0) return null

  return (
    <div
      className="px-6 py-3 flex items-center justify-between border-b"
      style={{ background: 'var(--cream)', borderColor: 'var(--border)' }}
    >
      <span className="text-sm" style={{ color: 'var(--ink)' }}>
        {KB.SELECTED(selectedCount)}
      </span>
      <button
        onClick={onDelete}
        className="px-3 py-1.5 text-sm rounded-lg flex items-center gap-1.5"
        style={{ background: 'var(--ink)', color: 'var(--cream)' }}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
        {KB.BATCH_DELETE}
      </button>
    </div>
  )
}