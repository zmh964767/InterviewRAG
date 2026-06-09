'use client'

import { useState, useCallback } from 'react'
import { useEffect } from 'react'

import { DeleteConfirmDialog } from '@/components/kb/DeleteConfirmDialog'
import { IngestModal } from '@/components/kb/IngestModal'
import { QuestionCard } from '@/components/kb/QuestionCard'
import { QuestionDetail } from '@/components/kb/QuestionDetail'
import { QuestionTable } from '@/components/kb/QuestionTable'
import { UndoToast } from '@/components/kb/UndoToast'
import { Sidebar } from '@/components/layout/Sidebar'
import { useKnowledgeBase } from '@/hooks/useKnowledgeBase'
import { deleteQuestion, getStats } from '@/lib/api'
import type { Question, StatsResponse } from '@/lib/types'

export default function KbPage() {
  const kb = useKnowledgeBase()

  // 详情抽屉选中项
  const [selected, setSelected] = useState<Question | null>(null)
  // 删除确认弹窗选中项
  const [toDelete, setToDelete] = useState<Question | null>(null)
  // 撤销 toast（缓存已删除题目的完整字段）
  const [undoBuffer, setUndoBuffer] = useState<Question | null>(null)
  // 导入模态框
  const [ingestOpen, setIngestOpen] = useState(false)

  // stats 给 Sidebar 用
  const [stats, setStats] = useState<StatsResponse | null>(null)
  useEffect(() => {
    getStats().then(setStats).catch(() => {})
  }, [])

  const handleSelect = useCallback((q: Question) => {
    setSelected(q)
  }, [])

  const handleAskDelete = useCallback((q: Question) => {
    setToDelete(q)
  }, [])

  const handleConfirmDelete = useCallback(async (q: Question) => {
    setToDelete(null)
    // 关闭详情抽屉
    setSelected(null)
    // 缓存到 undo buffer
    setUndoBuffer(q)
    // 乐观更新列表
    kb.removeItem(q.id)
    try {
      await deleteQuestion(q.id)
    } catch (e) {
      // 失败回滚
      kb.insertItem(q)
      setUndoBuffer(null)
      // eslint-disable-next-line no-alert
      alert(`删除失败: ${e instanceof Error ? e.message : '未知错误'}`)
    }
  }, [kb])

  const handleUndo = useCallback(() => {
    if (!undoBuffer) return
    // 调用 insertOne
    import('@/lib/api').then(({ insertOne }) => {
      insertOne({
        question: undoBuffer.question,
        answer: undoBuffer.answer,
        category: undoBuffer.category,
        difficulty: undoBuffer.difficulty,
        source: undoBuffer.source,
      })
        .then((q) => {
          kb.insertItem(q)
          setUndoBuffer(null)
        })
        .catch(() => {
          // 撤销失败（content_hash 冲突等）
          kb.refresh()
          setUndoBuffer(null)
          // eslint-disable-next-line no-alert
          alert('撤销失败，该题已存在')
        })
    })
  }, [undoBuffer, kb])

  const handleUndoDismiss = useCallback(() => {
    setUndoBuffer(null)
  }, [])

  return (
    <div className="flex h-screen" style={{ background: 'var(--cream)' }}>
      <Sidebar
        isOpen={true}
        onToggle={() => {}}
        stats={stats}
        conversations={[]}
        currentId={null}
        onCreateConversation={() => {}}
        onSwitchConversation={() => {}}
        onDeleteConversation={() => {}}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部工具栏 */}
        <header
          className="h-14 px-6 flex items-center gap-4 shrink-0 border-b"
          style={{ borderColor: 'var(--border)', background: 'rgba(250, 248, 245, 0.8)' }}
        >
          <h1
            className="text-lg tracking-tight"
            style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--ink)' }}
          >
            知识库管理
          </h1>
          <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
            共 {kb.total} 题
          </span>
          <div className="flex-1" />
          <button
            onClick={() => setIngestOpen(true)}
            className="px-3 py-1.5 text-sm rounded-lg flex items-center gap-1.5"
            style={{ background: 'var(--ink)', color: 'var(--cream)' }}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            导入
          </button>
        </header>

        {/* 过滤栏 */}
        <div
          className="px-6 py-3 flex flex-wrap items-center gap-3 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <input
            type="text"
            placeholder="搜索题面或答案..."
            value={kb.filters.q}
            onChange={(e) => kb.setQ(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg outline-none w-64"
            style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          />
          <select
            value={kb.filters.category}
            onChange={(e) => kb.setCategory(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg outline-none"
            style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          >
            <option value="">全部分类</option>
            {kb.categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            value={kb.filters.difficulty}
            onChange={(e) => kb.setDifficulty(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg outline-none"
            style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink)' }}
          >
            <option value="">全部难度</option>
            <option value="简单">简单</option>
            <option value="中等">中等</option>
            <option value="困难">困难</option>
          </select>
          {kb.isLoading && (
            <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>加载中...</span>
          )}
          {kb.error && (
            <span className="text-xs" style={{ color: 'var(--accent)' }}>{kb.error}</span>
          )}
        </div>

        {/* 列表区域 */}
        <div className="flex-1 overflow-hidden hidden md:flex flex-col">
          <QuestionTable
            items={kb.items}
            onSelect={handleSelect}
            onDelete={handleAskDelete}
          />
        </div>
        <div className="flex-1 overflow-y-auto md:hidden p-4">
          {kb.items.length === 0 ? (
            <p className="text-center text-sm py-8" style={{ color: 'var(--ink-muted)' }}>
              没有题目
            </p>
          ) : (
            kb.items.map((q) => (
              <QuestionCard
                key={q.id}
                question={q}
                onSelect={handleSelect}
                onDelete={handleAskDelete}
              />
            ))
          )}
        </div>

        {/* 分页 */}
        {kb.total > kb.size && (
          <div
            className="px-6 py-3 flex items-center justify-between border-t"
            style={{ borderColor: 'var(--border)' }}
          >
            <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
              第 {kb.page} 页 · 共 {Math.ceil(kb.total / kb.size)} 页
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => kb.setPage(Math.max(1, kb.page - 1))}
                disabled={kb.page <= 1}
                className="px-3 py-1 text-sm rounded disabled:opacity-30"
                style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
              >
                上一页
              </button>
              <button
                onClick={() => kb.setPage(kb.page + 1)}
                disabled={kb.page * kb.size >= kb.total}
                className="px-3 py-1 text-sm rounded disabled:opacity-30"
                style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 详情抽屉 */}
      <QuestionDetail
        question={selected}
        onClose={() => setSelected(null)}
        onDelete={handleAskDelete}
      />

      {/* 删除二次确认 */}
      <DeleteConfirmDialog
        question={toDelete}
        onCancel={() => setToDelete(null)}
        onConfirm={handleConfirmDelete}
      />

      {/* 撤销 toast */}
      <UndoToast
        question={undoBuffer}
        onUndo={handleUndo}
        onDismiss={handleUndoDismiss}
      />

      {/* 导入模态框 */}
      <IngestModal
        isOpen={ingestOpen}
        onClose={() => setIngestOpen(false)}
        onComplete={() => kb.refresh()}
      />
    </div>
  )
}
