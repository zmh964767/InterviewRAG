'use client'

import { useEffect, useState } from 'react'

import type { Question } from '@/lib/types'

interface UndoToastProps {
  question: Question | null
  onUndo: () => void
  onDismiss: () => void
}

const TOAST_DURATION_MS = 5000

export function UndoToast({ question, onUndo, onDismiss }: UndoToastProps) {
  const [progress, setProgress] = useState(100)

  useEffect(() => {
    if (!question) {
      setProgress(100)
      return
    }
    const startedAt = Date.now()
    const tick = setInterval(() => {
      const elapsed = Date.now() - startedAt
      const remaining = Math.max(0, 1 - elapsed / TOAST_DURATION_MS)
      setProgress(remaining * 100)
      if (remaining <= 0) {
        clearInterval(tick)
        onDismiss()
      }
    }, 50)
    return () => clearInterval(tick)
  }, [question, onDismiss])

  if (!question) return null

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex flex-col rounded-xl overflow-hidden shadow-lg"
      style={{ background: 'var(--paper)', border: '1px solid var(--border)', minWidth: 320 }}
    >
      <div className="px-4 py-3 flex items-center gap-3">
        <span style={{ color: 'var(--success)' }}>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </span>
        <div className="flex-1 text-sm" style={{ color: 'var(--ink)' }}>
          已删除 1 题
        </div>
        <button
          onClick={onUndo}
          className="text-sm font-medium px-2 py-1 rounded transition-colors"
          style={{ color: 'var(--accent)' }}
        >
          撤销
        </button>
      </div>
      <div className="h-0.5" style={{ background: 'var(--border-subtle)' }}>
        <div
          className="h-full transition-all"
          style={{ width: `${progress}%`, background: 'var(--accent)' }}
        />
      </div>
    </div>
  )
}
