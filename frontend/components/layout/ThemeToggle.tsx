'use client'

import { useTheme } from '@/contexts/ThemeContext'

/**
 * 主题切换按钮(icon only,emoji)
 *
 * - 当前 dark → 显示 ☀ + aria "切换到浅色主题"
 * - 当前 light → 显示 ☾ + aria "切换到暗色主题"
 * - keyboard 可达(Tab + Enter)+ aria-pressed 状态
 * - hover 颜色通过 globals.css 的 :hover 选择器(避免 React 重渲染冲突)
 */
export function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const isDark = theme === 'dark'
  return (
    <button
      onClick={toggle}
      aria-label={isDark ? '切换到浅色主题' : '切换到暗色主题'}
      aria-pressed={isDark}
      className="theme-toggle-btn p-2 rounded-lg"
    >
      <span aria-hidden="true">{isDark ? '☀' : '☾'}</span>
    </button>
  )
}