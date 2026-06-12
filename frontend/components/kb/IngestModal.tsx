'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { Modal } from '@/components/a11y/Modal'
import { ImportProgress } from '@/components/kb/ImportProgress'
import { useIngestTask } from '@/hooks/useIngestTask'
import { adminGetTaskStatus, adminSubmitIngestTask, adminUploadIngestFile } from '@/lib/api'

interface IngestModalProps {
  isOpen: boolean
  onClose: () => void
  onComplete: () => void
}

type Tab = 'file' | 'url' | 'path'

interface MultiTask {
  fileName: string
  taskId: string | null
  status: 'pending' | 'running' | 'done' | 'failed'
  ingested?: number
  duplicates?: number
  errors?: number
  errorMessage: string | null
}

const TAB_LABELS: Record<Tab, string> = {
  file: '上传文件',
  url: 'URL',
  path: '服务端路径',
}

export function IngestModal({ isOpen, onClose, onComplete }: IngestModalProps) {
  const [tab, setTab] = useState<Tab>('file')
  const [files, setFiles] = useState<File[]>([])
  const [url, setUrl] = useState('')
  const [path, setPath] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [hasCompleted, setHasCompleted] = useState(false)
  const ingest = useIngestTask()

  // 多任务状态
  const [multiTasks, setMultiTasks] = useState<MultiTask[]>([])
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const reset = useCallback(() => {
    setFiles([])
    setUrl('')
    setPath('')
    setSubmitting(false)
    setSubmitError(null)
    setHasCompleted(false)
    setMultiTasks([])
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
    ingest.stop()
  }, [ingest])

  const handleClose = useCallback(() => {
    reset()
    onClose()
  }, [reset, onClose])

  const handleSubmit = useCallback(async () => {
    setSubmitError(null)
    setSubmitting(true)
    try {
      if (tab === 'file') {
        // 多文件批量上传
        if (files.length === 0) {
          setSubmitError('请选择文件')
          setSubmitting(false)
          return
        }
        // 先创建占位任务条目
        setMultiTasks(files.map(f => ({
          fileName: f.name,
          taskId: null,
          status: 'pending' as const,
          errorMessage: null,
        })))

        // 并行提交所有文件
        const results = await Promise.all(
          files.map(async (file) => {
            const r = await adminUploadIngestFile(file)
            return { fileName: file.name, taskId: r.task_id }
          })
        )

        // 更新 taskId（useEffect 会自动启动 polling）
        setMultiTasks(prev => prev.map((t) => {
          const result = results.find(r => r.fileName === t.fileName)
          if (!result) return t
          return {
            ...t,
            taskId: result.taskId,
            status: 'running' as const,
          }
        }))
      } else if (tab === 'url') {
        if (!url.trim()) {
          setSubmitError('请输入 URL')
          setSubmitting(false)
          return
        }
        const r = await adminSubmitIngestTask(url.trim(), 'url')
        setMultiTasks([{
          fileName: url,
          taskId: r.task_id,
          status: 'running',
          errorMessage: null,
        }])
        setHasCompleted(false)
        ingest.start(r.task_id)
      } else {
        if (!path.trim()) {
          setSubmitError('请输入服务端路径')
          setSubmitting(false)
          return
        }
        const sourceType: 'md' | 'pdf' = path.endsWith('.pdf') ? 'pdf' : 'md'
        const r = await adminSubmitIngestTask(path.trim(), sourceType)
        setMultiTasks([{
          fileName: path,
          taskId: r.task_id,
          status: 'running',
          errorMessage: null,
        }])
        setHasCompleted(false)
        ingest.start(r.task_id)
      }
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }, [tab, files, url, path, ingest])

  // 自动启动 polling：当 multiTasks 有 running 任务时触发
  useEffect(() => {
    const hasRunning = multiTasks.some(t => t.taskId && t.status === 'running')
    if (!hasRunning) return

    if (pollingTimerRef.current) clearInterval(pollingTimerRef.current)

    const timer = setInterval(async () => {
      const taskIds = multiTasks
        .filter(t => t.taskId && t.status !== 'done' && t.status !== 'failed')
        .map(t => t.taskId!)
        .filter(Boolean)

      if (taskIds.length === 0) return

      const updates = await Promise.all(
        taskIds.map(async (taskId) => {
          const status = await adminGetTaskStatus(taskId)
          return { taskId, status }
        })
      )

      setMultiTasks(prev => {
        const next = prev.map(t => {
          const update = updates.find(u => u.taskId === t.taskId)
          if (!update) return t
          return {
            ...t,
            status: update.status.status as 'pending' | 'running' | 'done' | 'failed',
            ingested: update.status.ingested,
            duplicates: update.status.duplicates,
            errors: update.status.errors,
            errorMessage: update.status.error_message,
          }
        })
        const allDone = next.every(t => t.status === 'done' || t.status === 'failed')
        if (allDone && pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current)
          pollingTimerRef.current = null
          onComplete()
        }
        return next
      })
    }, 1000)

    pollingTimerRef.current = timer
    return () => clearInterval(timer)
  }, [multiTasks, onComplete])

  // 清理 polling
  useEffect(() => {
    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current)
      }
    }
  }, [])

  // 单任务完成时触发 onComplete
  useEffect(() => {
    if (tab !== 'file' && ingest.isTerminal && ingest.task?.status === 'done' && !hasCompleted) {
      setHasCompleted(true)
      onComplete()
    }
  }, [tab, ingest.isTerminal, ingest.task?.status, hasCompleted, onComplete])

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title="导入面试题"
      widthClassName="w-[40rem] max-w-[90vw]"
      titleNode={
        <header className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold" style={{ color: 'var(--ink)' }}>
            导入面试题
          </h3>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg"
            style={{ color: 'var(--ink-muted)' }}
            aria-label="关闭"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>
      }
    >
      {/* Tab 切换 */}
      <div className="flex gap-1 mb-4">
        {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="flex-1 py-2 text-sm rounded-lg transition-all"
            style={{
              background: tab === t ? 'var(--cream)' : 'transparent',
              color: tab === t ? 'var(--ink)' : 'var(--ink-muted)',
              border: tab === t ? '1px solid var(--border)' : '1px solid transparent',
            }}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      <div className="mb-4 min-h-[60px]">
        {tab === 'file' && (
          <div>
            <input
              type="file"
              multiple
              accept=".md,.pdf"
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
              className="block w-full text-sm"
              style={{ color: 'var(--ink)' }}
            />
            {files.length > 0 && (
              <p className="text-xs mt-2" style={{ color: 'var(--ink-muted)' }}>
                已选 {files.length} 个文件: {files.map(f => f.name).join(', ')}
              </p>
            )}
          </div>
        )}
        {tab === 'url' && (
          <input
            type="url"
            placeholder="https://example.com/questions"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg outline-none"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          />
        )}
        {tab === 'path' && (
          <div>
            <input
              type="text"
              placeholder="raw/Extra01-参考答案.md（仅允许 data/raw/ 目录下文件）"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none font-mono"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
            />
            <p className="text-xs mt-2" style={{ color: 'var(--ink-muted)' }}>
              后端会校验：必须相对、不可含 ..、不可为符号链接、必须在 data/ 内
            </p>
          </div>
        )}
      </div>

      {submitError && (
        <p className="text-xs mb-3" style={{ color: 'var(--accent)' }}>{submitError}</p>
      )}

      {/* 进度区 */}
      <div className="mb-4">
        {tab !== 'file' ? (
          <ImportProgress task={ingest.task} error={ingest.error} />
        ) : (
          multiTasks.map((task, i) => (
            <div key={i} className="p-2 rounded-lg" style={{ background: 'var(--cream)' }}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="truncate" style={{ maxWidth: '200px' }}>{task.fileName}</span>
                <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
                  {task.status === 'done' && '✅ 完成'}
                  {task.status === 'failed' && '❌ 失败'}
                  {task.status === 'running' && '⏳ 导入中...'}
                </span>
              </div>
              {task.status === 'running' && task.ingested !== undefined && (
                <ImportProgress task={{
                  task_id: task.taskId!,
                  status: 'running',
                  source_type: 'upload',
                  source: task.fileName,
                  total: (task.ingested || 0) + (task.duplicates || 0) + (task.errors || 0),
                  done: (task.ingested || 0) + (task.duplicates || 0) + (task.errors || 0),
                  ingested: task.ingested ?? 0,
                  duplicates: task.duplicates ?? 0,
                  errors: task.errors ?? 0,
                  started_at: '',
                  finished_at: null,
                  error_message: task.errorMessage || null,
                }} error={task.errorMessage} />
              )}
              {task.status === 'failed' && task.errorMessage && (
                <p className="text-xs mt-1" style={{ color: 'var(--accent)' }}>{task.errorMessage}</p>
              )}
            </div>
          ))
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-3 justify-end">
        <button
          onClick={handleClose}
          className="px-4 py-2 text-sm rounded-lg"
          style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
        >
          关闭
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting || ingest.isPolling || (tab === 'file' && multiTasks.some(t => t.status === 'running'))}
          className="px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-40"
          style={{ background: 'var(--ink)', color: 'var(--cream)' }}
        >
          {submitting || ingest.isPolling || (tab === 'file' && multiTasks.some(t => t.status === 'running'))
            ? '导入中...'
            : tab === 'file' && files.length > 1
              ? `批量导入 ${files.length} 个文件`
              : '开始导入'
          }
        </button>
      </div>
    </Modal>
  )
}