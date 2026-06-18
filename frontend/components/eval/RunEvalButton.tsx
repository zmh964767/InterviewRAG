'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { adminListEvalTasks, adminRunEval, adminCancelEval } from '@/lib/api'

interface RunEvalButtonProps {
  onComplete: () => void
}

type Mode = 'full' | 'ragas' | 'comparison' | 'sanity' | 'fast'

const MODE_OPTIONS: { value: Mode; label: string; desc?: string }[] = [
  { value: 'fast', label: '🚀 快速评估', desc: '抽样 20 题，约 3 分钟' },
  { value: 'full', label: '完整评估', desc: '全量 254 题，约 30 分钟' },
  { value: 'ragas', label: '仅 RAGAS' },
  { value: 'comparison', label: '仅策略对比' },
  { value: 'sanity', label: '冒烟测试' },
]

export function RunEvalButton({ onComplete }: RunEvalButtonProps) {
  const [mode, setMode] = useState<Mode>('fast')
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const startPolling = useCallback((taskId: string) => {
    stopPolling()
    pollingRef.current = setInterval(async () => {
      try {
        const list = await adminListEvalTasks()
        const t = list.tasks.find(x => x.task_id === taskId)
        if (!t) return
        if (t.total > 0) setProgress({ done: t.done, total: t.total })
        if (t.status === 'done' || t.status === 'failed') {
          stopPolling()
          setRunning(false)
          setProgress(null)
          if (t.status === 'done') onCompleteRef.current()
          else {
            const errMsg = typeof t.error_message === 'string' ? t.error_message : (t.error_message ? JSON.stringify(t.error_message) : '评估失败')
            console.error('[RunEval] task failed:', errMsg)
            setError(errMsg)
          }
        }
      } catch {
        // ignore poll error
      }
    }, 1500)
  }, [stopPolling])

  // 卸载时清 polling
  useEffect(() => () => stopPolling(), [stopPolling])

  // 挂载时检查是否有正在运行的评估任务（防止切页面后状态丢失）
  useEffect(() => {
    let cancelled = false
    adminListEvalTasks()
      .then((list) => {
        if (cancelled) return
        const active = list.tasks.find((t) => t.status === 'running')
        if (active) {
          setRunning(true)
          if (active.total > 0) setProgress({ done: active.done, total: active.total })
          startPolling(active.task_id)
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [startPolling])

  const handleRun = useCallback(async () => {
    setError(null)
    try {
      const { task_id } = await adminRunEval({ mode })
      setRunning(true)
      setProgress(null)
      startPolling(task_id)
    } catch (e) {
      console.error('[RunEval] error:', e, 'type:', typeof e, 'isError:', e instanceof Error)
      const msg = e instanceof Error ? e.message : (typeof e === 'object' ? JSON.stringify(e) : String(e))
      setError(msg || '触发失败')
    }
  }, [mode, startPolling])

  const handleCancel = useCallback(async () => {
    try {
      await adminCancelEval()
      stopPolling()
      setRunning(false)
      setProgress(null)
    } catch {
      // ignore
    }
  }, [stopPolling])

  return (
    <div className="flex items-center gap-2">
      <select
        value={mode}
        onChange={(e) => setMode(e.target.value as Mode)}
        disabled={running}
        className="px-2 py-1 text-xs rounded outline-none"
        style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
      >
        {MODE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {running ? (
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
            {progress ? `${progress.done}/${progress.total}` : '评估中...'}
          </span>
          <button
            onClick={handleCancel}
            className="px-3 py-1.5 text-sm rounded-lg"
            style={{ border: '1px solid var(--accent)', color: 'var(--accent)' }}
          >
            取消
          </button>
        </div>
      ) : (
        <button
          onClick={handleRun}
          className="px-3 py-1.5 text-sm rounded-lg"
          style={{ background: 'var(--ink)', color: 'var(--cream)' }}
        >
          运行评估
        </button>
      )}
      {error && (
        <span className="text-xs" style={{ color: 'var(--accent)' }}>{error}</span>
      )}
    </div>
  )
}
