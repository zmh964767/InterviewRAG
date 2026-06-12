'use client'

import { CHAT } from '@/lib/copy'

interface InlineErrorBannerProps {
  kind: 'aborted' | 'error'
  message: string
  onRetry?: () => void
  onDismiss: () => void
}

export function InlineErrorBanner({
  kind,
  message,
  onRetry,
  onDismiss,
}: InlineErrorBannerProps) {
  const title = kind === 'aborted' ? CHAT.ERROR.ABORTED : CHAT.ERROR.FAILED

  return (
    <div
      role="alert"
      className="flex items-stretch gap-3 mt-2 rounded-lg overflow-hidden animate-fade-in"
      style={{
        background: 'var(--accent-soft)',
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {/* Left red bar */}
      <div
        aria-hidden="true"
        className="shrink-0"
        style={{ width: 4, background: 'var(--accent)' }}
      />

      {/* Body */}
      <div className="flex-1 min-w-0 py-2.5 pr-2">
        <div
          className="text-xs font-medium mb-0.5"
          style={{ color: 'var(--ink)', fontFamily: 'var(--font-display)' }}
        >
          {title}
        </div>
        {message && (
          <div
            className="text-[11px] leading-relaxed"
            style={{ color: 'var(--ink-muted)' }}
          >
            {message}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 pr-2 shrink-0">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="px-2.5 py-1 text-[11px] rounded transition-all"
            style={{ color: 'var(--accent)' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--cream)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            {CHAT.ERROR.RETRY}
          </button>
        )}
        <button
          type="button"
          onClick={onDismiss}
          aria-label={CHAT.ARIA.DISMISS_ERROR}
          className="px-2.5 py-1 text-[11px] rounded transition-all"
          style={{ color: 'var(--ink-muted)' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--ink)'
            e.currentTarget.style.background = 'var(--cream)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--ink-muted)'
            e.currentTarget.style.background = 'transparent'
          }}
        >
          {CHAT.ERROR.DISMISS}
        </button>
      </div>
    </div>
  )
}
