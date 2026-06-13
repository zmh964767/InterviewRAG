'use client'

import { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react'
import type { ReactNode } from 'react'
import { getInitialTheme, THEME_STORAGE_KEY } from '@/lib/theme'
import type { Theme } from '@/lib/theme'

// =====================================================================
// ThemeContext: 全站明/暗主题状态管理
// 设计: ThemeProvider 唯一调 useState,5 个 page 共享同一数据源
// =====================================================================

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
  toggle: () => void
}

const ThemeContext = createContext<ThemeState | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  // SSR 默认 light;mount 后 useEffect 同步 inline script 已设的真实值
  const [theme, setThemeState] = useState<Theme>('light')

  // 同步 <html data-theme>(已被 inline script 写好)与 React state
  useEffect(() => {
    const current = getInitialTheme()
    setThemeState(current)
    document.documentElement.dataset.theme = current
  }, [])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
    document.documentElement.dataset.theme = t
    try {
      localStorage.setItem(THEME_STORAGE_KEY, t)
    } catch {
      // localStorage 不可用,降级仅写 DOM
    }
  }, [])

  const toggle = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }, [theme, setTheme])

  const value = useMemo<ThemeState>(
    () => ({ theme, setTheme, toggle }),
    [theme, setTheme, toggle],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}

// 重新导出,供 layout.tsx 在 head 中 inline 注入
export { THEME_INIT_SCRIPT } from '@/lib/theme'
