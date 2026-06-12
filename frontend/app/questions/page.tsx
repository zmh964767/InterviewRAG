'use client'

import { useState, useCallback, useEffect } from 'react'

import { QuestionCard } from '@/components/kb/QuestionCard'
import { QuestionDetail } from '@/components/kb/QuestionDetail'
import { QuestionTable } from '@/components/kb/QuestionTable'
import { Sidebar } from '@/components/layout/Sidebar'
import { Skeleton } from '@/components/ui/Skeleton'
import { useChatContext } from '@/contexts/ChatContext'
import { listQuestions } from '@/lib/api'
import { QUESTIONS } from '@/lib/copy'
import type { Question, QuestionListResponse } from '@/lib/types'

const DEFAULT_SIZE = 20

export default function QuestionsPage() {
  const [items, setItems] = useState<Question[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [q, setQ] = useState('')
  const [qDebounced, setQDebounced] = useState('')
  const [category, setCategory] = useState('')
  const [difficulty, setDifficulty] = useState('')

  const [selected, setSelected] = useState<Question | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const { conversations, currentId, createConversation, switchConversation, deleteConversation } = useChatContext()

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
      const res: QuestionListResponse = await listQuestions({
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

  return (
    <div className="flex h-screen" style={{ background: 'var(--cream)' }}>
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        conversations={conversations}
        currentId={currentId}
        onCreateConversation={() => createConversation()}
        onSwitchConversation={(id) => switchConversation(id)}
        onDeleteConversation={(id) => deleteConversation(id)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <header
          className="h-14 px-6 flex items-center gap-4 shrink-0 border-b"
          style={{ borderColor: 'var(--border)', background: 'rgba(250, 248, 245, 0.8)' }}
        >
          <h1 className="text-lg font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
            {QUESTIONS.TITLE}
          </h1>
          <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>{QUESTIONS.TOTAL(total)}</span>
        </header>

        {/* 过滤栏 */}
        <div className="px-6 py-3 flex flex-wrap items-center gap-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <input
            type="text"
            placeholder={QUESTIONS.SEARCH_PLACEHOLDER}
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

        {/* 列表：桌面表格 / 移动卡片 */}
        <div className="flex-1 overflow-hidden hidden md:flex flex-col">
          {isLoading && items.length === 0 ? (
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm border-collapse">
                <thead className="sticky top-0" style={{ background: 'var(--paper)', borderBottom: '1px solid var(--border)' }}>
                  <tr style={{ color: 'var(--ink-muted)' }}>
                    <th className="text-left px-4 py-3 font-medium" style={{ width: 80 }}>ID</th>
                    <th className="text-left px-4 py-3 font-medium">题面</th>
                    <th className="text-left px-4 py-3 font-medium" style={{ width: 120 }}>分类</th>
                    <th className="text-left px-4 py-3 font-medium" style={{ width: 80 }}>难度</th>
                    <th className="text-left px-4 py-3 font-medium" style={{ width: 140 }}>创建时间</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td className="px-4 py-3"><Skeleton className="h-4 w-14" /></td>
                      <td className="px-4 py-3"><Skeleton className="h-4 w-64" /></td>
                      <td className="px-4 py-3"><Skeleton className="h-4 w-16" /></td>
                      <td className="px-4 py-3"><Skeleton className="h-5 w-12" /></td>
                      <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <QuestionTable items={items} onSelect={setSelected} />
          )}
        </div>
        <div className="flex-1 overflow-y-auto md:hidden p-4">
          {items.length === 0 ? (
            <p className="text-center text-sm py-8" style={{ color: 'var(--ink-muted)' }}>{QUESTIONS.EMPTY}</p>
          ) : (
            items.map((q) => <QuestionCard key={q.id} question={q} onSelect={setSelected} />)
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
      </div>

      {/* 详情抽屉（只读，无删除按钮） */}
      <QuestionDetail question={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
