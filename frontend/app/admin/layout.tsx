'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { AdminAuthProvider, useAdminAuth } from '@/contexts/AdminAuthContext'
import Link from 'next/link'
import { A11Y } from '@/lib/copy'
import { ChangePasswordDialog } from './ChangePasswordDialog'

function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, isLoading, logout } = useAdminAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [showChangePwd, setShowChangePwd] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const hamburgerRef = useRef<HTMLButtonElement | null>(null)

  const isLoginPage = pathname === '/admin/login'

  useEffect(() => {
    if (!isLoading && !isLoggedIn && !isLoginPage) {
      router.replace(`/admin/login?redirect=${encodeURIComponent(pathname)}`)
    }
  }, [isLoading, isLoggedIn, isLoginPage, pathname, router])

  // 跟踪是否在移动端（<lg / 1024px），用于决定 inert 行为
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1023px)')
    setIsMobile(mq.matches)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // 路由切换时自动关闭移动端抽屉
  useEffect(() => {
    setMobileSidebarOpen(false)
  }, [pathname])

  // ESC 关闭移动端抽屉（排除 IME 组合）
  useEffect(() => {
    if (!mobileSidebarOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (e.isComposing) return
      setMobileSidebarOpen(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [mobileSidebarOpen])

  // 打开抽屉时锁定 body 滚动，关闭时还原
  useEffect(() => {
    if (!mobileSidebarOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [mobileSidebarOpen])

  // 打开时聚焦抽屉内首元素，关闭时还原到汉堡按钮
  useEffect(() => {
    if (mobileSidebarOpen) {
      const raf = requestAnimationFrame(() => {
        const aside = document.getElementById('admin-sidebar')
        if (!aside) return
        const first = aside.querySelector<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )
        if (first) {
          first.focus()
        } else {
          aside.focus()
        }
      })
      return () => cancelAnimationFrame(raf)
    }
    // 关闭时：仅在移动端把焦点还给汉堡按钮（桌面端不操作，避免误 focus 隐藏元素）
    if (isMobile) {
      hamburgerRef.current?.focus()
    }
    return undefined
  }, [mobileSidebarOpen, isMobile])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'var(--cream)' }}>
        <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>加载中...</p>
      </div>
    )
  }

  // 登录页无需布局
  if (isLoginPage) return <>{children}</>

  // 未登录不渲染内容（等待重定向）
  if (!isLoggedIn) return null

  const navItems = [
    { href: '/admin', label: '仪表盘', icon: 'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6z' },
    { href: '/admin/kb', label: '知识库', icon: 'M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25' },
    { href: '/admin/eval', label: '评估', icon: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z' },
  ]

  return (
    <div className="flex h-screen" style={{ background: 'var(--cream)' }}>
      <a href="#main-content" className="skip-link">{A11Y.SKIP_TO_MAIN}</a>

      {/* 移动端汉堡按钮 — 仅 <lg 显示 */}
      <button
        ref={hamburgerRef}
        onClick={() => setMobileSidebarOpen(true)}
        className="lg:hidden fixed top-3 left-3 z-30 p-2 rounded-lg transition-colors"
        style={{ background: 'var(--paper)', border: '1px solid var(--border)', color: 'var(--ink-muted)' }}
        aria-label={A11Y.MENU}
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      {/* 移动端遮罩 — 打开时显示，点击关闭 */}
      {mobileSidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/50 transition-opacity"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Admin Sidebar — 移动端滑入抽屉，桌面端常驻布局流 */}
      <aside
        id="admin-sidebar"
        tabIndex={-1}
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          w-64 shrink-0 flex flex-col border-r
          transform transition-transform duration-300 ease-in-out
          ${mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
        style={{ background: 'var(--paper)', borderColor: 'var(--border)' }}
        aria-label="管理后台导航"
        // 仅移动端关闭时 inert：桌面端侧边栏常驻可见可交互（避免 Tab 跳过）
        inert={isMobile && !mobileSidebarOpen ? true : undefined}
      >
        <div className="h-14 px-5 flex items-center border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent)' }}>
              <span className="text-sm" style={{ fontFamily: 'var(--font-display)', color: '#ffffff', fontWeight: 600 }}>A</span>
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>管理后台</div>
            </div>
          </div>
          {/* 抽屉内关闭按钮 — 仅移动端显示 */}
          <button
            onClick={() => setMobileSidebarOpen(false)}
            className="ml-auto p-1.5 rounded-lg transition-colors lg:hidden"
            style={{ color: 'var(--ink-muted)' }}
            aria-label="关闭菜单"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== '/admin' && pathname?.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all"
                style={{
                  background: isActive ? 'var(--nav-active-bg)' : 'transparent',
                  color: isActive ? 'var(--ink)' : 'var(--ink-muted)',
                  border: isActive ? '1px solid var(--border-subtle)' : '1px solid transparent',
                }}
              >
                <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
                </svg>
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="px-3 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <button
            onClick={() => setShowChangePwd(true)}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors"
            style={{ color: 'var(--ink-muted)' }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--nav-active-bg)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
            修改密码
          </button>
          <button
            onClick={() => { logout(); router.replace('/admin/login') }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors"
            style={{ color: 'var(--ink-muted)' }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--nav-active-bg)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
            </svg>
            退出登录
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto">
        {children}
      </main>

      <ChangePasswordDialog isOpen={showChangePwd} onClose={() => setShowChangePwd(false)} />
    </div>
  )
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminAuthProvider>
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </AdminAuthProvider>
  )
}
