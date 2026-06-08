'use client'

import type { Question } from '@/lib/types'

interface QuestionDetailProps {
  question: Question | null
  onClose: () => void
  onDelete: (q: Question) => void
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/)
  if (m) return m[0].replace('T', ' ')
  return iso
}

export function QuestionDetail({ question, onClose, onDelete }: QuestionDetailProps) {
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
            <button
              onClick={() => onDelete(question)}
              className="text-sm px-3 py-1.5 rounded-lg transition-colors"
              style={{ color: 'var(--accent)', border: '1px solid var(--accent)' }}
            >
              删除
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
          <Section label="ID" value={<span className="font-mono text-xs">{question.id}</span>} />

          <div className="grid grid-cols-2 gap-4">
            <Section label="分类" value={question.category} />
            <Section label="难度" value={question.difficulty} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Section label="来源" value={question.source || '—'} />
            <Section label="创建时间" value={formatTime(question.created_at)} />
          </div>

          <Section
            label="题目"
            value={<div className="whitespace-pre-wrap leading-relaxed">{question.question}</div>}
          />

          <Section
            label="参考答案"
            value={
              <div className="whitespace-pre-wrap leading-relaxed" style={{ color: 'var(--ink-light)' }}>
                {question.answer}
              </div>
            }
          />

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

function Section({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p
        className="text-xs font-medium uppercase tracking-widest mb-2"
        style={{ color: 'var(--ink-muted)', letterSpacing: '0.1em' }}
      >
        {label}
      </p>
      <div className="text-sm" style={{ color: 'var(--ink)' }}>{value}</div>
    </div>
  )
}
