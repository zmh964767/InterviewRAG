'use client'

import { useCallback, useEffect, useState } from 'react'

import { Modal } from '@/components/a11y/Modal'
import { ImportProgress } from '@/components/kb/ImportProgress'
import { useIngestTask } from '@/hooks/useIngestTask'
import { adminSubmitIngestTask, adminUploadIngestFile } from '@/lib/api'

interface IngestModalProps {
  isOpen: boolean
  onClose: () => void
  onComplete: () => void
}

type Tab = 'file' | 'url' | 'path'

const TAB_LABELS: Record<Tab, string> = {
  file: '上传文件',
  url: 'URL',
  path: '服务端路径',
}

export function IngestModal({ isOpen, onClose, onComplete }: IngestModalProps) {
  const [tab, setTab] = useState<Tab>('file')
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [path, setPath] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  // 防止 onComplete 重复触发（status 从其他变成 done 时只触发一次）
  const [hasCompleted, setHasCompleted] = useState(false)
  const ingest = useIngestTask()

  const reset = useCallback(() => {
    setFile(null)
    setUrl('')
    setPath('')
    setSubmitting(false)
    setSubmitError(null)
    setHasCompleted(false)
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
      let taskId: string
      if (tab === 'file') {
        if (!file) {
          setSubmitError('请选择文件')
          setSubmitting(false)
          return
        }
        const r = await adminUploadIngestFile(file)
        taskId = r.task_id
      } else if (tab === 'url') {
        if (!url.trim()) {
          setSubmitError('请输入 URL')
          setSubmitting(false)
          return
        }
        const r = await adminSubmitIngestTask(url.trim(), 'url')
        taskId = r.task_id
      } else {
        if (!path.trim()) {
          setSubmitError('请输入服务端路径')
          setSubmitting(false)
          return
        }
        // 简单判断扩展名决定 source_type
        const sourceType: 'md' | 'pdf' = path.endsWith('.pdf') ? 'pdf' : 'md'
        const r = await adminSubmitIngestTask(path.trim(), sourceType)
        taskId = r.task_id
      }
      setHasCompleted(false)  // 重新开始任务时重置
      ingest.start(taskId)
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }, [tab, file, url, path, ingest])

  // 任务完成（status=done）时只触发一次 onComplete
  // 用 useEffect 避免在渲染函数体里调用造成无限循环
  useEffect(() => {
    if (ingest.isTerminal && ingest.task?.status === 'done' && !hasCompleted) {
      setHasCompleted(true)
      onComplete()
    }
  }, [ingest.isTerminal, ingest.task?.status, hasCompleted, onComplete])

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title="导入面试题"
      widthClassName="w-[36rem] max-w-[90vw]"
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
      <div className="mb-4 min-h-[80px]">
        {tab === 'file' && (
          <input
            type="file"
            accept=".md,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm"
            style={{ color: 'var(--ink)' }}
          />
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
        <ImportProgress task={ingest.task} error={ingest.error} />
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
          disabled={submitting || ingest.isPolling}
          className="px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-40"
          style={{ background: 'var(--ink)', color: 'var(--cream)' }}
        >
          {ingest.isPolling ? '导入中...' : '开始导入'}
        </button>
      </div>
    </Modal>
  )
}
