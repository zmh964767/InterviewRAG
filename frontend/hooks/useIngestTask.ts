'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { adminGetTaskStatus } from '@/lib/api'
import type { TaskStatusResponse } from '@/lib/types'

const POLL_INTERVAL_MS = 1000

interface UseIngestTaskResult {
  task: TaskStatusResponse | null
  isPolling: boolean
  isTerminal: boolean
  error: string | null
  start: (taskId: string) => void
  stop: () => void
}

export function useIngestTask(): UseIngestTaskResult {
  const [task, setTask] = useState<TaskStatusResponse | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const taskIdRef = useRef<string | null>(null)

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const start = useCallback(
    (taskId: string) => {
      setError(null)
      taskIdRef.current = taskId
      setIsPolling(true)

      const poll = async () => {
        try {
          const status = await adminGetTaskStatus(taskId)
          setTask(status)
          if (status.status === 'done' || status.status === 'failed') {
            stop()
          }
        } catch (e) {
          // 404 = task 丢失（服务重启等）
          if (e instanceof Error && e.message.includes('404')) {
            setError('任务已丢失（可能服务重启）')
          } else {
            setError(e instanceof Error ? e.message : '查询失败')
          }
          stop()
        }
      }

      // 立即拉一次
      void poll()
      intervalRef.current = setInterval(poll, POLL_INTERVAL_MS)
    },
    [stop],
  )

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  const isTerminal = task?.status === 'done' || task?.status === 'failed'

  return { task, isPolling, isTerminal, error, start, stop }
}
