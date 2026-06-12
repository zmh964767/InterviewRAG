'use client'

import { Modal } from '@/components/a11y/Modal'
import type { Question } from '@/lib/types'

interface DeleteConfirmDialogProps {
  question: Question | null
  onCancel: () => void
  onConfirm: (q: Question) => void
}

export function DeleteConfirmDialog({ question, onCancel, onConfirm }: DeleteConfirmDialogProps) {
  return (
    <Modal open={!!question} onClose={onCancel} title="删除题目？">
      <p className="text-sm mb-4" style={{ color: 'var(--ink-muted)' }}>
        此操作可撤销（5 秒内）。被删除的题目将无法被聊天检索。
      </p>

      {question && (
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
      )}

      <div className="flex gap-3 justify-end">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm rounded-lg transition-all"
          style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
        >
          取消
        </button>
        <button
          onClick={() => question && onConfirm(question)}
          className="px-4 py-2 text-sm font-medium rounded-lg transition-all"
          style={{ background: 'var(--accent)', color: 'var(--cream)' }}
        >
          确认删除
        </button>
      </div>
    </Modal>
  )
}
