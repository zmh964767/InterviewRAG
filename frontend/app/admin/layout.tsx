'use client'

import { useEffect, useState } from 'react'
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

  const isLoginPage = pathname === '/admin/login'

  useEffect(() => {
    if (!isLoading && !isLoggedIn && !isLoginPage) {
      router.replace(`/admin/login?redirect=${encodeURIComponent(pathname)}`)
    }
  }, [isLoading, isLoggedIn, isLoginPage, pathname, router])

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
      {/* Admin Sidebar */}
      <aside className="w-64 shrink-0 flex flex-col border-r" style={{ background: 'var(--paper)', borderColor: 'var(--border)' }}>
        <div className="h-14 px-5 flex items-center border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent)' }}>
              <span className="text-sm" style={{ fontFamily: 'var(--font-display)', color: '#ffffff', fontWeight: 600 }}>A</span>
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>管理后台</div>
            </div>
          </div>
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
