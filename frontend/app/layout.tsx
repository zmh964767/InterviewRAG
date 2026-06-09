'use client'

import { ChatProvider } from '@/contexts/ChatContext'
import { useConversations } from '@/hooks/useConversations'
import './globals.css'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // 在 layout 渲染 useConversations，确保跨路由共享同一份 conversations state
  // 关键：它必须被实际调用以触发 useState/useEffect
  return (
    <html lang="zh-CN">
      <head>
        <title>InterviewRAG - 面试题库问答系统</title>
        <meta name="description" content="基于 RAG 的面试题库问答系统，提供精准的面试准备" />
      </head>
      <body className="antialiased">
        <ChatProvider>
          <ConversationsBootstrap>{children}</ConversationsBootstrap>
        </ChatProvider>
      </body>
    </html>
  )
}

// 在 layout 内部调用 useConversations 以保持单一实例
function ConversationsBootstrap({ children }: { children: React.ReactNode }) {
  // 调用 hook 建立 localStorage 同步 + state
  useConversations()
  return <>{children}</>
}
