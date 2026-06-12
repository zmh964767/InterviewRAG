'use client'

import { useState, useCallback, useEffect, useRef } from 'react'

import { DeleteConfirmDialog } from '@/components/kb/DeleteConfirmDialog'
import { IngestModal } from '@/components/kb/IngestModal'
import { QuestionCard } from '@/components/kb/QuestionCard'
import { QuestionDetail } from '@/components/kb/QuestionDetail'
import { QuestionTable } from '@/components/kb/QuestionTable'
import { UndoToast } from '@/components/kb/UndoToast'
import { BatchToolbar } from '@/components/kb/BatchToolbar'
import { BatchDeleteDialog } from '@/components/kb/BatchDeleteDialog'
import { ErrorBanner } from '@/components/ui/ErrorBanner'
import { Skeleton } from '@/components/ui/Skeleton'
import { adminBatchDelete, adminDeleteQuestion, adminInsertOne, adminListQuestions } from '@/lib/api'
import { ADMIN, KB, QUESTIONS } from '@/lib/copy'
import type { Question, QuestionListResponse } from '@/lib/types'

const DEFAULT_SIZE = 20

export default function AdminKbPage() {
  // 分页 + 列表状态
  const [items, setItems] = useState<Question[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 筛选
  const [q, setQ] = useState('')
  const [qDebounced, setQDebounced] = useState('')
  const [category, setCategory] = useState('')
  const [difficulty, setDifficulty] = useState('')

  // UI 状态
  const [selected, setSelected] = useState<Question | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [toDelete, setToDelete] = useState<Question | null>(null)
  const [undoBuffer, setUndoBuffer] = useState<Question | null>(null)
  const [ingestOpen, setIngestOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const actionErrorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 搜索 debounce
  useEffect(() => {
    const timer = setTimeout(() => setQDebounced(q), 300)
    return () => clearTimeout(timer)
  }, [q])

  // 筛选变化回到第1页
  useEffect(() => { setPage(1) }, [qDebounced, category, difficulty])

  // 加载数据
  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res: QuestionListResponse = await adminListQuestions({
        page, size: DEFAULT_SIZE, q: qDebounced, category, difficulty,
      })
      setItems(res.items)
      setTotal(res.total)
      setCategories(res.categories)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setIsLoading(false)
    }
  }, [page, qDebounced, category, difficulty])

  useEffect(() => { void load() }, [load])

  const refresh = useCallback(() => { void load() }, [load])

  // 设置 actionError 并 5 秒后自动清除
  const setActionErrorWithAutoDismiss = useCallback((msg: string) => {
    setActionError(msg)
    if (actionErrorTimerRef.current) {
      clearTimeout(actionErrorTimerRef.current)
    }
    actionErrorTimerRef.current = setTimeout(() => {
      setActionError(null)
      actionErrorTimerRef.current = null
    }, 5000)
  }, [])

  // 卸载时清理 timer
  useEffect(() => {
    return () => {
      if (actionErrorTimerRef.current) {
        clearTimeout(actionErrorTimerRef.current)
      }
    }
  }, [])

  // 删除逻辑
  const handleConfirmDelete = useCallback(async (q: Question) => {
    setToDelete(null)
    setSelected(null)
    setUndoBuffer(q)
    setItems((prev) => prev.filter((i) => i.id !== q.id))
    setTotal((prev) => Math.max(0, prev - 1))
    try {
      await adminDeleteQuestion(q.id)
    } catch (e) {
      setItems((prev) => [q, ...prev])
      setTotal((prev) => prev + 1)
      setUndoBuffer(null)
      setActionErrorWithAutoDismiss(
        `${ADMIN.ALERTS.DELETE_FAILED}: ${e instanceof Error ? e.message : '未知错误'}`,
      )
    }
  }, [setActionErrorWithAutoDismiss])

  // 撤销逻辑
  const handleUndo = useCallback(() => {
    if (!undoBuffer) return
    adminInsertOne({
      question: undoBuffer.question,
      answer: undoBuffer.answer,
      category: undoBuffer.category,
      difficulty: undoBuffer.difficulty,
      source: undoBuffer.source,
    })
      .then((newQ) => {
        setItems((prev) => [newQ, ...prev])
        setTotal((prev) => prev + 1)
        setUndoBuffer(null)
      })
      .catch(() => {
        refresh()
        setUndoBuffer(null)
        setActionErrorWithAutoDismiss(ADMIN.ALERTS.UNDO_FAILED)
      })
  }, [undoBuffer, refresh, setActionErrorWithAutoDismiss])

  // 多选相关
  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleToggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      const allIds = items.map(i => i.id)
      const allSelected = allIds.length > 0 && allIds.every(id => prev.has(id))
      const next = new Set(prev)
      if (allSelected) {
        allIds.forEach(id => next.delete(id))
      } else {
        allIds.forEach(id => next.add(id))
      }
      return next
    })
  }, [items])

  const handleBatchDelete = useCallback(async () => {
    const ids = Array.from(selectedIds)
    const removedItems = items.filter(i => selectedIds.has(i.id))
    setBatchDeleteOpen(false)
    setSelectedIds(new Set())
    setItems((prev) => prev.filter(i => !selectedIds.has(i.id)))
    setTotal((prev) => Math.max(0, prev - ids.length))
    try {
      const { deleted } = await adminBatchDelete(ids)
      setActionErrorWithAutoDismiss(KB.DELETE_SUCCESS(deleted))
    } catch (e) {
      setItems((prev) => [...removedItems, ...prev])
      setTotal((prev) => prev + removedItems.length)
      setActionErrorWithAutoDismiss(
        `${ADMIN.ALERTS.DELETE_FAILED}: ${e instanceof Error ? e.message : '未知错误'}`,
      )
    }
  }, [selectedIds, items, setActionErrorWithAutoDismiss])

  return (
    <div className="flex flex-col h-full">
      {/* 顶部工具栏 */}
      <header
        className="h-14 px-6 flex items-center gap-4 shrink-0 border-b"
        style={{ borderColor: 'var(--border)', background: 'rgba(250, 248, 245, 0.8)' }}
      >
        <h1 className="text-lg font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
          {KB.TITLE}
        </h1>
        <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>{KB.TOTAL(total)}</span>
        <div className="flex-1" />
        <button
          onClick={() => setIngestOpen(true)}
          className="px-3 py-1.5 text-sm rounded-lg flex items-center gap-1.5"
          style={{ background: 'var(--ink)', color: 'var(--cream)' }}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          {KB.IMPORT}
        </button>
      </header>

      {/* 过滤栏 */}
      <div className="px-6 py-3 flex flex-wrap items-center gap-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <input
          type="text"
          placeholder={KB.SEARCH_PLACEHOLDER}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-lg outline-none w-64"
          style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-lg outline-none"
          style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
        >
          <option value="">全部分类</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-lg outline-none"
          style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
        >
          <option value="">全部难度</option>
          <option value="简单">简单</option>
          <option value="中等">中等</option>
          <option value="困难">困难</option>
        </select>
        {isLoading && <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>加载中...</span>}
        {error && <span className="text-xs" style={{ color: 'var(--accent)' }}>{error}</span>}
      </div>

      {/* 动作错误条(替代 window.alert) */}
      {actionError && (
        <div className="px-6 pt-3">
          <ErrorBanner
            message={actionError}
            onDismiss={() => setActionError(null)}
          />
        </div>
      )}

      {/* 批量操作工具栏 */}
      <BatchToolbar selectedCount={selectedIds.size} onDelete={() => setBatchDeleteOpen(true)} />

      {/* 列表 */}
      <div className="flex-1 overflow-hidden hidden md:flex flex-col">
        {isLoading && items.length === 0 ? (
          <div className="flex-1 overflow-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0" style={{ background: 'var(--paper)', borderBottom: '1px solid var(--border)' }}>
                <tr style={{ color: 'var(--ink-muted)' }}>
                  <th className="text-left px-4 py-3 font-medium" style={{ width: 48 }} />
                  <th className="text-left px-4 py-3 font-medium" style={{ width: 80 }}>ID</th>
                  <th className="text-left px-4 py-3 font-medium">题面</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ width: 120 }}>分类</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ width: 80 }}>难度</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ width: 140 }}>创建时间</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ width: 80 }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-4" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-14" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-64" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-16" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-5 w-12" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-4 py-3 text-right"><Skeleton className="h-6 w-12 ml-auto" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <QuestionTable
            items={items}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
            onToggleSelectAll={handleToggleSelectAll}
            onSelect={setSelected}
            onDelete={setToDelete}
          />
        )}
      </div>
      <div className="flex-1 overflow-y-auto md:hidden p-4">
        {items.length === 0 ? (
          <p className="text-center text-sm py-8" style={{ color: 'var(--ink-muted)' }}>{KB.EMPTY}</p>
        ) : (
          items.map((q) => <QuestionCard key={q.id} question={q} onSelect={setSelected} onDelete={setToDelete} />)
        )}
      </div>

      {/* 分页 */}
      {total > DEFAULT_SIZE && (
        <div className="px-6 py-3 flex items-center justify-between border-t" style={{ borderColor: 'var(--border)' }}>
          <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
            第 {page} 页 · 共 {Math.ceil(total / DEFAULT_SIZE)} 页
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="px-3 py-1 text-sm rounded disabled:opacity-30"
              style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
            >{QUESTIONS.PREV_PAGE}</button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={page * DEFAULT_SIZE >= total}
              className="px-3 py-1 text-sm rounded disabled:opacity-30"
              style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
            >{QUESTIONS.NEXT_PAGE}</button>
          </div>
        </div>
      )}

      {/* 弹窗 */}
      <QuestionDetail
        question={selected}
        categories={categories}
        onClose={() => setSelected(null)}
        onDelete={setToDelete}
        onSave={(updated) => {
          setItems(prev => prev.map(i => i.id === updated.id ? updated : i))
          setSelected(null)
        }}
      />
      <DeleteConfirmDialog question={toDelete} onCancel={() => setToDelete(null)} onConfirm={handleConfirmDelete} />
      <UndoToast question={undoBuffer} onUndo={handleUndo} onDismiss={() => setUndoBuffer(null)} />
      <IngestModal isOpen={ingestOpen} onClose={() => setIngestOpen(false)} onComplete={refresh} />
      <BatchDeleteDialog
        isOpen={batchDeleteOpen}
        items={items.filter(i => selectedIds.has(i.id))}
        onCancel={() => setBatchDeleteOpen(false)}
        onConfirm={handleBatchDelete}
      />
    </div>
  )
}
