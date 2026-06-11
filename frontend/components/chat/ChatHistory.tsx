'use client'

import { useEffect, useRef } from 'react'
import type { Message } from '@/lib/types'
import { ChatMessage } from './ChatMessage'

interface ChatHistoryProps {
  messages: Message[]
  isLoading: boolean
  onSend: (message: string) => void
  onRegenerate?: () => void
}

export function ChatHistory({ messages, isLoading, onSend, onRegenerate }: ChatHistoryProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const prevLenRef = useRef(messages.length)
  // 标记组件是否刚挂载（用于"已挂载但 messages.length 增长"才是新消息；
  // "刚挂载 + messages 已经有很多"是路由切换恢复，不算新消息）
  const mountedRef = useRef(false)

  // 只在消息数量增加时自动滚动（切换对话/加载历史不触发）
  useEffect(() => {
    if (mountedRef.current && messages.length > prevLenRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    mountedRef.current = true
    prevLenRef.current = messages.length
  }, [messages.length])

  // Welcome screen
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center max-w-xl animate-fade-in">
          {/* Decorative line */}
          <div className="flex items-center justify-center gap-3 mb-8">
            <div className="h-px w-12" style={{ background: 'var(--border)' }} />
            <svg className="w-5 h-5" style={{ color: 'var(--accent)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <div className="h-px w-12" style={{ background: 'var(--border)' }} />
          </div>

          {/* Title */}
          <h1
            className="text-4xl mb-3 tracking-tight stagger-1 animate-slide-up"
            style={{ fontFamily: 'var(--font-display)', fontWeight: 300, color: 'var(--ink)' }}
          >
            InterviewRAG
          </h1>
          <p
            className="text-sm mb-10 stagger-2 animate-slide-up"
            style={{ color: 'var(--ink-muted)', maxWidth: '28rem', margin: '0 auto 2.5rem' }}
          >
            基于 RAG 的智能面试题库问答系统<br />
            输入你的面试问题，获得专业回答
          </p>

          {/* Feature grid */}
          <div className="grid grid-cols-3 gap-6 mb-10 stagger-3 animate-slide-up">
            {[
              { icon: '01', title: '语义检索', desc: '混合检索策略' },
              { icon: '02', title: '来源引用', desc: '答案可追溯' },
              { icon: '03', title: '多轮对话', desc: '上下文连贯' },
            ].map((f) => (
              <div key={f.icon} className="text-center">
                <div className="text-xs font-medium mb-2 tracking-widest" style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                  {f.icon}
                </div>
                <div className="text-sm font-medium mb-0.5" style={{ color: 'var(--ink)' }}>{f.title}</div>
                <div className="text-xs" style={{ color: 'var(--ink-muted)' }}>{f.desc}</div>
              </div>
            ))}
          </div>

          {/* Divider */}
          <div className="flex items-center gap-4 mb-8 stagger-4 animate-slide-up">
            <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
            <span className="text-xs" style={{ color: 'var(--ink-muted)', letterSpacing: '0.1em' }}>试试这些</span>
            <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
          </div>

          {/* Quick start - clickable */}
          <div className="flex flex-wrap justify-center gap-3 stagger-4 animate-slide-up">
            {[
              'Transformer 自注意力机制',
              'RAG 的基本流程',
              'RLHF 训练流程',
              'MoE 如何工作',
            ].map((q) => (
              <button
                key={q}
                onClick={() => onSend(q)}
                className="px-5 py-2 text-sm rounded-full transition-all"
                style={{ border: '1px solid var(--border)', color: 'var(--ink-light)', background: 'var(--cream)' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--accent)'
                  e.currentTarget.style.color = 'var(--accent)'
                  e.currentTarget.style.background = 'var(--accent-soft)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.color = 'var(--ink-light)'
                  e.currentTarget.style.background = 'var(--cream)'
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // Messages
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        {messages.map((message, index) => {
          const isLastAssistant = message.role === 'assistant' && index === messages.length - 1
          return (
            <ChatMessage
              key={message.id}
              message={message}
              isStreaming={isLastAssistant && isLoading}
              onRegenerate={isLastAssistant ? onRegenerate : undefined}
            />
          )
        })}

        {/* Loading */}
        {isLoading && messages.length > 0 && messages[messages.length - 1]?.role === 'user' && (
          <div className="flex gap-4 animate-fade-in mb-8">
            <div className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--ink)' }}>
              <span className="text-xs" style={{ fontFamily: 'var(--font-display)', color: 'var(--cream)' }}>R</span>
            </div>
            <div className="flex-1">
              <div
                className="inline-flex items-center gap-3 px-4 py-3 rounded-xl text-sm"
                style={{ background: 'var(--paper)', color: 'var(--ink-muted)', border: '1px solid var(--border-subtle)' }}
              >
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: 'var(--ink-muted)', animationDelay: '-0.3s' }} />
                  <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: 'var(--ink-muted)', animationDelay: '-0.15s' }} />
                  <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: 'var(--ink-muted)' }} />
                </div>
                <span className="text-xs">检索知识库中...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
