'use client'

import { useState, useCallback, useEffect } from 'react'
import type { Question } from '@/lib/types'
import { adminUpdateQuestion } from '@/lib/api'
import { formatTime } from '@/lib/utils'

interface QuestionDetailProps {
  question: Question | null
  categories?: string[]
  onClose: () => void
  onDelete?: (q: Question) => void
  onSave?: (q: Question) => void
}

const DIFFICULTY_OPTIONS = ['简单', '中等', '困难']
const CUSTOM_CATEGORY = '__custom__'

export function QuestionDetail({ question, categories = [], onClose, onDelete, onSave }: QuestionDetailProps) {
  const [editCategory, setEditCategory] = useState('')
  const [editDifficulty, setEditDifficulty] = useState('中等')
  const [editQuestion, setEditQuestion] = useState('')
  const [editAnswer, setEditAnswer] = useState('')
  const [isCustomCategory, setIsCustomCategory] = useState(false)
  const [customCategory, setCustomCategory] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // question 变化时重置编辑状态
  useEffect(() => {
    if (!question) return
    const inList = categories.includes(question.category)
    setEditCategory(inList ? question.category : CUSTOM_CATEGORY)
    setIsCustomCategory(!inList)
    setCustomCategory(inList ? '' : question.category)
    setEditDifficulty(question.difficulty)
    setEditQuestion(question.question)
    setEditAnswer(question.answer)
    setError(null)
  }, [question, categories])

  const handleCategoryChange = useCallback((value: string) => {
    if (value === CUSTOM_CATEGORY) {
      setIsCustomCategory(true)
      setEditCategory(CUSTOM_CATEGORY)
    } else {
      setIsCustomCategory(false)
      setEditCategory(value)
      setCustomCategory('')
    }
  }, [])

  const finalCategory = isCustomCategory ? customCategory : editCategory

  const handleSave = useCallback(async () => {
    if (!question) return
    if (!finalCategory.trim()) {
      setError('分类不能为空')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const updated = await adminUpdateQuestion(question.id, {
        question: editQuestion,
        answer: editAnswer,
        category: finalCategory.trim(),
        difficulty: editDifficulty,
      })
      onSave?.(updated)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }, [question, editQuestion, editAnswer, finalCategory, editDifficulty, onSave, onClose])

  if (!question) return null

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(26, 22, 18, 0.2)' }}
        onClick={onClose}
      />

      {/* Drawer */}
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 flex flex-col animate-slide-in"
        style={{
          width: 'min(560px, 90vw)',
          background: 'var(--paper)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        <header
          className="h-14 px-5 flex items-center justify-between shrink-0 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <button
            onClick={onClose}
            className="text-sm flex items-center gap-1"
            style={{ color: 'var(--ink-muted)' }}
          >
            ← 返回
          </button>
          <div className="flex gap-2">
            {onDelete && question && (
              <button
                onClick={() => onDelete(question)}
                className="text-sm px-3 py-1.5 rounded-lg transition-colors"
                style={{ color: 'var(--accent)', border: '1px solid var(--accent)' }}
              >
                删除
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-sm px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
              style={{ background: 'var(--ink)', color: 'var(--cream)' }}
            >
              {saving ? '保存中...' : '保存'}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg transition-colors"
              style={{ color: 'var(--ink-muted)' }}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {error && (
            <div className="p-3 rounded-lg text-sm" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b' }}>
              {error}
            </div>
          )}

          <Section label="ID" value={<span className="font-mono text-xs">{question.id}</span>} />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label text="分类" />
              {isCustomCategory ? (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={customCategory}
                    onChange={(e) => setCustomCategory(e.target.value)}
                    className="flex-1 px-3 py-2 text-sm rounded-lg outline-none"
                    style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
                    placeholder="输入分类名称"
                  />
                  <button
                    onClick={() => { setIsCustomCategory(false); setEditCategory(categories[0] || ''); setCustomCategory('') }}
                    className="text-xs px-2 py-1 rounded"
                    style={{ color: 'var(--ink-muted)', border: '1px solid var(--border-subtle)' }}
                  >
                    取消
                  </button>
                </div>
              ) : (
                <select
                  value={editCategory}
                  onChange={(e) => handleCategoryChange(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg outline-none"
                  style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
                >
                  {categories.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                  <option value={CUSTOM_CATEGORY}>+ 自定义...</option>
                </select>
              )}
            </div>
            <div>
              <Label text="难度" />
              <select
                value={editDifficulty}
                onChange={(e) => setEditDifficulty(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg outline-none"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
              >
                {DIFFICULTY_OPTIONS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Section label="来源" value={question.source || '—'} />
            <Section label="创建时间" value={formatTime(question.created_at, true)} />
          </div>

          <div>
            <Label text="题目" />
            <textarea
              value={editQuestion}
              onChange={(e) => setEditQuestion(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none resize-y"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink)' }}
            />
          </div>

          <div>
            <Label text="参考答案" />
            <textarea
              value={editAnswer}
              onChange={(e) => setEditAnswer(e.target.value)}
              rows={6}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none resize-y"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--ink-light)' }}
            />
          </div>

          <Section
            label="标签"
            value={
              question.tags && question.tags.length > 0
                ? (
                  <div className="flex flex-wrap gap-2">
                    {question.tags.map((t) => (
                      <span
                        key={t}
                        className="text-xs px-2 py-0.5 rounded"
                        style={{ background: 'var(--cream)', border: '1px solid var(--border-subtle)' }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )
                : <span style={{ color: 'var(--ink-muted)' }}>[无]</span>
            }
          />
        </div>
      </aside>
    </>
  )
}

function Label({ text }: { text: string }) {
  return (
    <p
      className="text-xs font-medium uppercase tracking-widest mb-2"
      style={{ color: 'var(--ink-muted)', letterSpacing: '0.1em' }}
    >
      {text}
    </p>
  )
}

function Section({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <Label text={label} />
      <div className="text-sm" style={{ color: 'var(--ink)' }}>{value}</div>
    </div>
  )
}
