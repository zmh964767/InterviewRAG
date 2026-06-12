'use client'

import type { CSSProperties } from 'react'
import { CHAT } from '@/lib/copy'

interface ErrorBannerProps {
  message: string
  onRetry?: () => void
  variant?: 'card' | 'inline'
}

/**
 * 暖色编辑风格的错误条
 * - role="alert" + aria-live="polite" 让读屏自动播报
 * - card: 完整卡片样式,适合占据整个面板
 * - inline: 紧凑行内样式,适合嵌入统计卡等小区域
 */
export function ErrorBanner({ message, onRetry, variant = 'card' }: ErrorBannerProps) {
  if (variant === 'inline') {
    const dotStyle: CSSProperties = { background: 'var(--accent)' }
    const textStyle: CSSProperties = { color: 'var(--ink-muted)' }
    const btnStyle: CSSProperties = { color: 'var(--accent)' }
    return (
      <div
        role="alert"
        aria-live="polite"
        className="flex items-center gap-2 text-sm"
      >
        <span
          aria-hidden="true"
          className="inline-block w-2 h-2 rounded-full shrink-0"
          style={dotStyle}
        />
        <span style={textStyle}>{message}</span>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="ml-1 underline underline-offset-2 hover:opacity-80"
            style={btnStyle}
          >
            {CHAT.ERROR.RETRY}
          </button>
        )}
      </div>
    )
  }

  const wrapStyle: CSSProperties = {
    background: 'var(--paper)',
    border: '1px solid var(--accent)',
    borderLeft: '4px solid var(--accent)',
  }
  const textStyle: CSSProperties = { color: 'var(--ink)' }
  const btnStyle: CSSProperties = {
    color: 'var(--accent)',
    border: '1px solid var(--accent)',
  }
  return (
    <div
      role="alert"
      aria-live="polite"
      className="flex items-center gap-3 p-4 rounded-xl animate-fade-in"
      style={wrapStyle}
    >
      <span className="flex-1 text-sm" style={textStyle}>
        {message}
      </span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="text-sm px-3 py-1 rounded-md hover:opacity-80"
          style={btnStyle}
        >
          {CHAT.ERROR.RETRY}
        </button>
      )}
    </div>
  )
}
