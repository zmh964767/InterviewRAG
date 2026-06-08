'use client'

import type { Question } from '@/lib/types'

interface DeleteConfirmDialogProps {
  question: Question | null
  onCancel: () => void
  onConfirm: (q: Question) => void
}

export function DeleteConfirmDialog({ question, onCancel, onConfirm }: DeleteConfirmDialogProps) {
  if (!question) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(26, 22, 18, 0.3)', backdropFilter: 'blur(4px)' }}
      onClick={onCancel}
    >
      <div
        className="w-[28rem] max-w-[90vw] p-6 rounded-2xl"
        style={{ background: 'var(--paper)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-lg)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--ink)' }}>
          删除题目？
        </h3>
        <p className="text-sm mb-4" style={{ color: 'var(--ink-muted)' }}>
          此操作可撤销（5 秒内）。被删除的题目将无法被聊天检索。
        </p>

        <div className="mb-3 p-3 rounded-lg text-sm" style={{ background: 'var(--cream)', border: '1px solid var(--border-subtle)' }}>
          <p className="font-mono text-xs mb-2" style={{ color: 'var(--ink-muted)' }}>
            {question.id.slice(0, 8)}
          </p>
          <p className="line-clamp-2 mb-2" style={{ color: 'var(--ink)' }}>
            <strong>题：</strong>{question.question}
          </p>
          <p className="line-clamp-3 text-xs" style={{ color: 'var(--ink-muted)' }}>
            <strong>答案：</strong>{question.answer}
          </p>
        </div>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm rounded-lg transition-all"
            style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
          >
            取消
          </button>
          <button
            onClick={() => onConfirm(question)}
            className="px-4 py-2 text-sm font-medium rounded-lg transition-all"
            style={{ background: 'var(--accent)', color: 'var(--cream)' }}
          >
            确认删除
          </button>
        </div>
      </div>
    </div>
  )
}
