'use client'

import { ChatProvider } from '@/contexts/ChatContext'
import { A11Y } from '@/lib/copy'
import './globals.css'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <head>
        <title>InterviewRAG - 面试题库问答系统</title>
        <meta name="description" content="基于 RAG 的面试题库问答系统，提供精准的面试准备" />
      </head>
      <body className="antialiased">
        <a href="#main-content" className="skip-link">{A11Y.SKIP_TO_MAIN}</a>
        <ChatProvider>{children}</ChatProvider>
      </body>
    </html>
  )
}
