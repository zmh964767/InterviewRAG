'use client'

import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="text-center">
              <p className="text-sm mb-3" style={{ color: 'var(--ink-muted)' }}>
                渲染出错了
              </p>
              <button
                onClick={() => this.setState({ hasError: false })}
                className="px-4 py-2 text-sm rounded-lg transition-all"
                style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
              >
                重试
              </button>
            </div>
          </div>
        )
      )
    }
    return this.props.children
  }
}
