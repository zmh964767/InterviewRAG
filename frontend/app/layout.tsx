'use client'

import { ChatProvider } from '@/contexts/ChatContext'
import { ThemeProvider, THEME_INIT_SCRIPT } from '@/contexts/ThemeContext'
import { A11Y } from '@/lib/copy'
import './globals.css'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" data-theme="light">
      <head>
        <title>InterviewRAG - 面试题库问答系统</title>
        <meta name="description" content="基于 RAG 的面试题库问答系统，提供精准的面试准备" />
        {/* 防闪烁:在 React hydration 之前读 localStorage/matchMedia 设 data-theme */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <a href="#main-content" className="skip-link">{A11Y.SKIP_TO_MAIN}</a>
        <ThemeProvider>
          <ChatProvider>{children}</ChatProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}