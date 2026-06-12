'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'
import type { Message } from '@/lib/types'
import { SourceCard } from '@/components/sources/SourceCard'
import { InlineErrorBanner } from './InlineErrorBanner'

interface ChatMessageProps {
  message: Message
  isStreaming?: boolean
  onRegenerate?: () => void
  onContinue?: () => void
  error?: { kind: 'aborted' | 'error'; message: string } | null
  onDismissError?: () => void
}

export function ChatMessage({
  message,
  isStreaming,
  onRegenerate,
  onContinue,
  error,
  onDismissError,
}: ChatMessageProps) {
  const [showSources, setShowSources] = useState(true)
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  // ---- Markdown 节流:流式时每 50ms 解析一次,减少 ReactMarkdown 重复调用 ----
  const THROTTLE_MS = 50
  const [committedContent, setCommittedContent] = useState(message.content)
  const lastCommitRef = useRef(Date.now())

  useEffect(() => {
    if (!isStreaming) {
      // 流结束:立即 commit 最新内容
      setCommittedContent(message.content)
      lastCommitRef.current = Date.now()
      return
    }
    const now = Date.now()
    const elapsed = now - lastCommitRef.current
    if (elapsed >= THROTTLE_MS) {
      setCommittedContent(message.content)
      lastCommitRef.current = now
    } else {
      const t = setTimeout(() => {
        setCommittedContent(message.content)
        lastCommitRef.current = Date.now()
      }, THROTTLE_MS - elapsed)
      return () => clearTimeout(t)
    }
  }, [message.content, isStreaming])

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [message.content])

  return (
    <div className={`flex gap-4 mb-8 animate-fade-in ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className="shrink-0">
        {isUser ? (
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent)', color: 'var(--cream)' }}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
          </div>
        ) : (
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--ink)', color: 'var(--cream)' }}>
            <span className="text-xs" style={{ fontFamily: 'var(--font-display)', fontWeight: 600 }}>R</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        {/* Label */}
        <div className={`flex items-center gap-2 mb-1.5 ${isUser ? 'justify-end' : ''}`}>
          <span className="text-xs font-medium" style={{ color: 'var(--ink-muted)' }}>
            {isUser ? '你' : 'InterviewRAG'}
          </span>
          <span className="text-xs" style={{ color: 'var(--border)' }}>·</span>
          <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
            {new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

        {/* Bubble */}
        <div
          className={`inline-block text-left max-w-full rounded-xl px-4 py-3 ${isUser ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
          style={{
            background: isUser ? 'var(--ink)' : 'var(--paper)',
            color: isUser ? 'var(--cream)' : 'var(--ink)',
            border: isUser ? 'none' : '1px solid var(--border-subtle)',
          }}
        >
          {message.content ? (
            isUser ? (
              <div className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</div>
            ) : (
              <div className="text-sm leading-relaxed markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight]}
                >
                  {committedContent}
                </ReactMarkdown>
              </div>
            )
          ) : (
            <div className="flex items-center gap-1.5 py-1">
              <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: isUser ? 'var(--cream)' : 'var(--ink-muted)', animationDelay: '-0.3s' }} />
              <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: isUser ? 'var(--cream)' : 'var(--ink-muted)', animationDelay: '-0.15s' }} />
              <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: isUser ? 'var(--cream)' : 'var(--ink-muted)' }} />
            </div>
          )}
        </div>

        {/* Inline error banner (assistant messages only) */}
        {!isUser && error && onDismissError && (
          <InlineErrorBanner
            kind={error.kind}
            message={error.message}
            onRetry={onContinue ?? onRegenerate}
            onDismiss={onDismissError}
          />
        )}

        {/* Actions (assistant messages only) */}
        {!isUser && message.content && !isStreaming && !error && (
          <div className="flex items-center gap-1 mt-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all"
              style={{ color: copied ? 'var(--success)' : 'var(--ink-muted)' }}
              onMouseEnter={(e) => { if (!copied) e.currentTarget.style.color = 'var(--accent)' }}
              onMouseLeave={(e) => { if (!copied) e.currentTarget.style.color = 'var(--ink-muted)' }}
            >
              {copied ? (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                </svg>
              )}
              {copied ? '已复制' : '复制'}
            </button>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all"
                style={{ color: 'var(--ink-muted)' }}
                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)' }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ink-muted)' }}
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                </svg>
                重新生成
              </button>
            )}
          </div>
        )}

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1.5 text-xs transition-colors"
              style={{ color: 'var(--ink-muted)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ink-muted)' }}
            >
              <svg
                className="w-3 h-3 transition-transform"
                style={{ transform: showSources ? 'rotate(90deg)' : 'rotate(0deg)' }}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span>{message.sources.length} 个相关来源</span>
            </button>
            {showSources && (
              <div className="mt-2 space-y-2 animate-slide-up">
                {message.sources.map((source, i) => (
                  <SourceCard key={i} source={source} index={i} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
