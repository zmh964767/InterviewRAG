'use client'

import { useEffect, useRef } from 'react'
import type { Question } from '@/lib/types'

interface QuestionTableProps {
  items: Question[]
  selectedIds?: Set<string>
  onToggleSelect?: (id: string) => void
  onToggleSelectAll?: () => void
  onSelect?: (q: Question) => void
  onDelete?: (q: Question) => void
}

const DIFFICULTY_COLORS: Record<string, string> = {
  简单: 'var(--success)',
  中等: 'var(--ink-muted)',
  困难: 'var(--accent)',
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/)
  if (m) return `${m[1]} ${m[2]}`
  return iso
}

export function QuestionTable({ items, selectedIds = new Set(), onToggleSelect = () => {}, onToggleSelectAll = () => {}, onSelect, onDelete }: QuestionTableProps) {
  const indeterminateRef = useRef<HTMLInputElement>(null)

  // 更新表头 checkbox 的 indeterminate 状态
  useEffect(() => {
    if (indeterminateRef.current) {
      const allSelected = items.length > 0 && items.every(i => selectedIds.has(i.id))
      const someSelected = items.some(i => selectedIds.has(i.id))
      indeterminateRef.current.checked = allSelected
      indeterminateRef.current.indeterminate = someSelected && !allSelected
    }
  }, [selectedIds, items])

  if (items.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm" style={{ color: 'var(--ink-muted)' }}>
        没有题目
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead className="sticky top-0" style={{ background: 'var(--paper)', borderBottom: '1px solid var(--border)' }}>
          <tr style={{ color: 'var(--ink-muted)' }}>
            <th className="text-left px-4 py-3 font-medium" style={{ width: 48 }}>
              <input
                type="checkbox"
                ref={indeterminateRef}
                onChange={onToggleSelectAll}
                className="cursor-pointer"
                aria-label="全选当前页"
              />
            </th>
            <th className="text-left px-4 py-3 font-medium" style={{ width: 80 }}>ID</th>
            <th className="text-left px-4 py-3 font-medium">题面</th>
            <th className="text-left px-4 py-3 font-medium" style={{ width: 120 }}>分类</th>
            <th className="text-left px-4 py-3 font-medium" style={{ width: 80 }}>难度</th>
            <th className="text-left px-4 py-3 font-medium" style={{ width: 140 }}>创建时间</th>
            {onDelete && <th className="text-right px-4 py-3 font-medium" style={{ width: 80 }}>操作</th>}
          </tr>
        </thead>
        <tbody>
          {items.map((q) => (
            <tr
              key={q.id}
              onClick={() => onSelect?.(q)}
              className="cursor-pointer transition-colors"
              style={{ borderBottom: '1px solid var(--border-subtle)' }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--nav-active-bg)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              <td className="px-4 py-3 text-center">
                <input
                  type="checkbox"
                  checked={selectedIds.has(q.id)}
                  onChange={() => onToggleSelect(q.id)}
                  onClick={(e) => e.stopPropagation()}
                  className="cursor-pointer"
                  aria-label={`选择 ${q.question}`}
                />
              </td>
              <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--ink-muted)' }}>
                {q.id.slice(0, 8)}
              </td>
              <td className="px-4 py-3" style={{ color: 'var(--ink-light)' }}>
                <div className="truncate" style={{ maxWidth: 480 }}>{q.question}</div>
              </td>
              <td className="px-4 py-3" style={{ color: 'var(--ink-light)' }}>{q.category}</td>
              <td className="px-4 py-3">
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background: 'var(--nav-active-bg)',
                    color: DIFFICULTY_COLORS[q.difficulty] ?? 'var(--ink-muted)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  {q.difficulty}
                </span>
              </td>
              <td className="px-4 py-3 text-xs" style={{ color: 'var(--ink-muted)' }}>
                {formatTime(q.created_at)}
              </td>
              {onDelete && (
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(q) }}
                    className="text-xs px-2 py-1 rounded transition-colors"
                    style={{ color: 'var(--ink-muted)', border: '1px solid var(--border-subtle)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)'; e.currentTarget.style.borderColor = 'var(--accent)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ink-muted)'; e.currentTarget.style.borderColor = 'var(--border-subtle)' }}
                  >
                    删除
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
