'use client'

import type { TaskStatusResponse } from '@/lib/types'

interface ImportProgressProps {
  task: TaskStatusResponse | null
  error: string | null
}

export function ImportProgress({ task, error }: ImportProgressProps) {
  if (error) {
    return (
      <div
        className="p-3 rounded-lg text-sm"
        style={{ background: 'var(--cream)', border: '1px solid var(--accent)', color: 'var(--accent)' }}
      >
        {error}
      </div>
    )
  }

  if (!task) {
    return (
      <p className="text-xs" style={{ color: 'var(--ink-muted)' }}>暂无任务</p>
    )
  }

  if (task.status === 'pending' || task.status === 'running') {
    const pct = task.total > 0 ? Math.round((task.done / task.total) * 100) : 0
    return (
      <div className="space-y-2">
        <div className="flex justify-between text-sm" style={{ color: 'var(--ink-light)' }}>
          <span>正在导入 {task.source} ...</span>
          <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>
            {task.done} / {task.total} ({pct}%)
          </span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border-subtle)' }}>
          <div
            className="h-full transition-all duration-300"
            style={{ width: `${pct}%`, background: 'var(--accent)' }}
          />
        </div>
      </div>
    )
  }

  if (task.status === 'done') {
    return (
      <div
        className="p-3 rounded-lg text-sm space-y-1"
        style={{ background: 'var(--cream)', border: '1px solid var(--border-subtle)' }}
      >
        <p style={{ color: 'var(--ink)' }}>
          <strong>导入完成</strong> · {task.source}
        </p>
        <p className="text-xs" style={{ color: 'var(--ink-muted)' }}>
          新增 {task.ingested} · 重复 {task.duplicates} · 失败 {task.errors}
        </p>
      </div>
    )
  }

  // failed
  return (
    <div
      className="p-3 rounded-lg text-sm"
      style={{ background: 'var(--cream)', border: '1px solid var(--accent)', color: 'var(--accent)' }}
    >
      导入失败：{task.error_message || '未知错误'}
    </div>
  )
}
