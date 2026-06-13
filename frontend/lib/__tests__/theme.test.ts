import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getInitialTheme, THEME_STORAGE_KEY } from '@/lib/theme'

describe('getInitialTheme', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  function setMatchMedia(prefersDark: boolean) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: prefersDark && query === '(prefers-color-scheme: dark)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  }

  it('returns stored "dark" when localStorage has dark preference', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    expect(getInitialTheme()).toBe('dark')
  })

  it('returns stored "light" when localStorage has light preference', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
    expect(getInitialTheme()).toBe('light')
  })

  it('returns "light" when no stored theme and system prefers light', () => {
    setMatchMedia(false)
    expect(getInitialTheme()).toBe('light')
  })

  it('returns "dark" when no stored theme and system prefers dark', () => {
    setMatchMedia(true)
    expect(getInitialTheme()).toBe('dark')
  })

  it('ignores invalid localStorage values and falls back to system preference', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'invalid-value')
    setMatchMedia(true)
    expect(getInitialTheme()).toBe('dark')
  })

  it('returns "light" when matchMedia returns false for dark query', () => {
    // matchMedia mocked to return false (system light), no stored theme → light
    setMatchMedia(false)
    expect(getInitialTheme()).toBe('light')
  })
})
