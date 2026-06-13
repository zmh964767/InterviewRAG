// =====================================================================
// theme.ts: 主题纯函数模块(无 React)
// 设计: 主题切换核心逻辑,ThemeProvider 与 layout inline script 共用
// =====================================================================

export type Theme = 'light' | 'dark'
export const THEME_STORAGE_KEY = 'theme'

/**
 * 读取初始主题(SSR safe)
 *
 * 优先级:
 *   1. localStorage.theme(用户手动选过)
 *   2. window.matchMedia('(prefers-color-scheme: dark)')(首次访问跟随系统)
 *   3. 'light'(SSR / 旧浏览器 / 隐私模式降级)
 */
export function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // localStorage 不可用(隐私模式)
  }
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  return prefersDark ? 'dark' : 'light'
}

/**
 * 客户端 inline init script(由 layout.tsx 注入 <head>)
 *
 * 必须在 React hydration 之前同步执行,以避免浅色帧闪烁。
 *
 * 设计原则:
 * - 静态字符串,无变量注入 → dangerouslySetInnerHTML 安全
 * - IIFE + try/catch → 即使 localStorage 不可用也安全降级到 light
 * - 逻辑与 getInitialTheme() 保持一致
 */
export const THEME_INIT_SCRIPT = `
(function() {
  try {
    var stored = localStorage.getItem('theme');
    var theme = stored === 'light' || stored === 'dark'
      ? stored
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.dataset.theme = theme;
  } catch (e) {
    document.documentElement.dataset.theme = 'light';
  }
})();
`.trim()