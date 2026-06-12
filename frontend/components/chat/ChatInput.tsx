'use client'

import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { CHAT } from '@/lib/copy'

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading: boolean
  onStop?: () => void
}

export function ChatInput({ onSend, isLoading, onStop }: ChatInputProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 100)}px`
    }
  }, [input])

  const handleSend = () => {
    if (!input.trim() || isLoading) return
    onSend(input.trim())
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="px-6 py-4 shrink-0 border-t" style={{ borderColor: 'var(--border)', background: 'var(--cream)' }}>
      <div className="max-w-3xl mx-auto">
        {/* Suggested questions */}
        {input === '' && (
          <div className="mb-3 flex flex-wrap gap-2 animate-fade-in">
            {[
              'Transformer 自注意力机制',
              'RAG 的基本流程',
              'RLHF 训练流程',
              'MoE 如何工作',
            ].map((q) => (
              <button
                key={q}
                onClick={() => { setInput(q); textareaRef.current?.focus() }}
                className="px-3 py-1.5 text-xs rounded-lg transition-all"
                style={{
                  border: '1px solid var(--border)',
                  color: 'var(--ink-muted)',
                  background: 'var(--paper)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--accent)'
                  e.currentTarget.style.color = 'var(--accent)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.color = 'var(--ink-muted)'
                }}
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div
          className="flex items-end gap-2 rounded-xl p-2 transition-all"
          style={{
            background: 'var(--paper)',
            border: '1px solid var(--border)',
          }}
          onFocus={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--accent)' }}
          onBlur={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)' }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isLoading ? CHAT.PLACEHOLDER.STREAMING : CHAT.PLACEHOLDER.IDLE
            }
            rows={1}
            className="flex-1 resize-none bg-transparent px-3 py-2 text-sm focus:outline-none"
            style={{
              color: 'var(--ink)',
              fontFamily: 'var(--font-body)',
              maxHeight: '100px',
            }}
          />
          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              aria-label={CHAT.ARIA.STOP}
              className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-all"
              style={{
                background: 'var(--ink)',
                color: 'var(--cream)',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.opacity = '0.85'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = '1'
              }}
            >
              {/* Stop icon: two vertical bars */}
              <svg
                className="w-3.5 h-3.5"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <rect x="6" y="5" width="4" height="14" rx="1" />
                <rect x="14" y="5" width="4" height="14" rx="1" />
              </svg>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              aria-label={CHAT.ARIA.SEND}
              className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-all"
              style={{
                background: input.trim() && !isLoading ? 'var(--ink)' : 'var(--border)',
                color: input.trim() && !isLoading ? 'var(--cream)' : 'var(--ink-muted)',
                cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
              }}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          )}
        </div>

        {/* Hint */}
        <p className="text-center text-xs mt-2" style={{ color: 'var(--ink-muted)' }}>
          <kbd className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'var(--border-subtle)', fontFamily: 'var(--font-mono)' }}>Enter</kbd>
          {' '}发送 ·{' '}
          <kbd className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'var(--border-subtle)', fontFamily: 'var(--font-mono)' }}>Shift+Enter</kbd>
          {' '}换行
        </p>
      </div>
    </div>
  )
}
