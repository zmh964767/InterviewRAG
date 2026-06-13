'use client'

import { useState, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { useAdminAuth } from '@/contexts/AdminAuthContext'

export default function AdminLoginPage() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { login, isLoggedIn } = useAdminAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  const redirect = searchParams.get('redirect') || '/admin'

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim()) return
    setLoading(true)
    setError(null)

    const ok = await login(password)
    if (ok) {
      router.replace(redirect)
    } else {
      setError('密码错误')
      setLoading(false)
    }
  }, [password, login, router, redirect])

  // 已登录则跳转
  if (isLoggedIn) {
    router.replace(redirect)
    return null
  }

  return (
    <div className="flex min-h-screen items-center justify-center" style={{ background: 'var(--cream)' }}>
      <div className="fixed top-4 right-4 z-50"><ThemeToggle /></div>
      <div
        className="w-full max-w-sm p-8 rounded-2xl"
        style={{ background: 'var(--paper)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-lg)' }}
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent)' }}>
            <span className="text-base" style={{ fontFamily: 'var(--font-display)', color: '#ffffff', fontWeight: 600 }}>A</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
              管理员登录
            </h1>
            <p className="text-xs" style={{ color: 'var(--ink-muted)' }}>InterviewRAG 管理后台</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm mb-1.5" style={{ color: 'var(--ink-light)' }}>管理密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入管理员密码"
              className="w-full px-4 py-2.5 text-sm rounded-lg outline-none transition-all"
              style={{
                background: 'var(--cream)',
                border: error ? '1px solid var(--accent)' : '1px solid var(--border)',
                color: 'var(--ink)',
              }}
              autoFocus
            />
            {error && (
              <p className="text-xs mt-1.5" style={{ color: 'var(--accent)' }}>{error}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || !password.trim()}
            className="w-full py-2.5 text-sm font-medium rounded-lg transition-all disabled:opacity-50"
            style={{ background: 'var(--ink)', color: 'var(--cream)' }}
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}
