'use client'

import type { Question } from '@/lib/types'
import { Modal } from '@/components/a11y/Modal'
import { KB } from '@/lib/copy'

interface BatchDeleteDialogProps {
  isOpen: boolean
  items: Question[]
  onCancel: () => void
  onConfirm: () => void
}

export function BatchDeleteDialog({ isOpen, items, onCancel, onConfirm }: BatchDeleteDialogProps) {
  const count = items.length

  return (
    <Modal
      open={isOpen}
      onClose={onCancel}
      title="确认批量删除"
      widthClassName="w-[28rem] max-w-[90vw]"
    >
      <p className="text-sm mb-3" style={{ color: 'var(--ink)' }}>
        {KB.BATCH_DELETE_CONFIRM(count)}
      </p>

      {count > 0 && (
        <div className="mb-4">
          <p className="text-xs mb-2" style={{ color: 'var(--ink-muted)' }}>将删除以下题目：</p>
          <ul className="space-y-1 text-xs">
            {items.slice(0, 3).map((item) => (
              <li key={item.id} className="truncate" style={{ color: 'var(--ink-light)' }}>
                • {item.question}
              </li>
            ))}
            {count > 3 && (
              <li className="truncate" style={{ color: 'var(--ink-muted)' }}>
                … 等 {count} 条
              </li>
            )}
          </ul>
        </div>
      )}

      <div className="flex gap-3 justify-end">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm rounded-lg"
          style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
        >
          取消
        </button>
        <button
          onClick={onConfirm}
          className="px-4 py-2 text-sm font-medium rounded-lg"
          style={{ background: 'var(--accent)', color: 'var(--cream)' }}
        >
          确认删除
        </button>
      </div>
    </Modal>
  )
}