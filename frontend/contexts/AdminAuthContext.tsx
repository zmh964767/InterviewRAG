'use client'

import { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react'
import type { ReactNode } from 'react'

const API_BASE = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8080' : ''))
  : ''

interface AdminAuthState {
  isLoggedIn: boolean
  isLoading: boolean
  token: string | null  // 保留字段供 adminHeaders() 向后兼容，实际 token 在 httpOnly cookie 中
  login: (password: string) => Promise<boolean>
  logout: () => void
}

const AdminAuthContext = createContext<AdminAuthState | null>(null)

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // 启动时通过 /api/auth/me 检查 httpOnly cookie 是否有效
  useEffect(() => {
    fetch(`${API_BASE}/api/auth/me`, { credentials: 'include' })
      .then(res => {
        if (res.ok) {
          // cookie 有效 — token 在 httpOnly cookie 里，前端无需存储
          setToken('cookie-authenticated')
        } else {
          setToken(null)
        }
      })
      .catch(() => setToken(null))
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (password: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
        credentials: 'include',  // 接收 Set-Cookie
      })
      if (!res.ok) return false
      setToken('cookie-authenticated')
      return true
    } catch {
      return false
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',  // 让 Set-Cookie 清除 cookie
      })
    } catch {
      // 即使后端不可达也清除前端状态
    }
    setToken(null)
  }, [])

  const value = useMemo(
    () => ({ isLoggedIn: !!token, isLoading, token, login, logout }),
    [token, isLoading, login, logout],
  )

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}

export function useAdminAuth(): AdminAuthState {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) throw new Error('useAdminAuth must be used inside AdminAuthProvider')
  return ctx
}
