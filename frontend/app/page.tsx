'use client'

import { useState, useCallback } from 'react'
import { Modal } from '@/components/a11y/Modal'
import { ChatHistory } from '@/components/chat/ChatHistory'
import { ChatInput } from '@/components/chat/ChatInput'
import { Sidebar } from '@/components/layout/Sidebar'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useChatContext } from '@/contexts/ChatContext'
import { A11Y } from '@/lib/copy'

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  // 统一从 ChatContext 消费（conversations + 流式 + CRUD）
  const {
    streamingConvId,
    conversations,
    currentId,
    currentMessages,
    createConversation,
    switchConversation,
    deleteConversation,
    sendMessage,
    abort,
  } = useChatContext()

  // 是否当前正在生成（后台流式不打断用户体验，但 UI 只对当前会话显示 loading/停止按钮）
  const isLoading = streamingConvId === currentId

  // 停止生成：调用 context.abort() 中断当前流
  const handleStop = useCallback(() => {
    abort()
  }, [abort])

  // 发送消息：确保有 convId → 调 sendMessage（user + 空 ai 由内部写入）
  const handleSend = useCallback(
    (content: string) => {
      if (!content.trim()) return
      let convId = currentId
      if (!convId || conversations.length === 0) {
        convId = createConversation()
      }
      if (convId) {
        void sendMessage(content, convId)
      }
    },
    [currentId, conversations.length, createConversation, sendMessage],
  )

  // 新建对话
  const handleNewChat = useCallback(() => {
    createConversation()
  }, [createConversation])

  // 切换对话
  const handleSwitchConversation = useCallback(
    (id: string) => {
      switchConversation(id)
    },
    [switchConversation],
  )

  // 重新生成：找到最后一条 user 消息重发
  const handleRegenerate = useCallback(() => {
    if (currentMessages.length < 2 || !currentId) return
    const lastUserMsg = [...currentMessages].reverse().find((m) => m.role === 'user')
    if (lastUserMsg) {
      handleSend(lastUserMsg.content)
    }
  }, [currentMessages, currentId, handleSend])

  // 删除对话（先确认）
  const handleDeleteConversation = useCallback((id: string) => {
    setDeleteConfirmId(id)
  }, [])

  const confirmDelete = useCallback(() => {
    if (deleteConfirmId) {
      deleteConversation(deleteConfirmId)
      setDeleteConfirmId(null)
    }
  }, [deleteConfirmId, deleteConversation])

  return (
    <div className="flex h-screen" style={{ background: 'var(--cream)' }}>
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        conversations={conversations}
        currentId={currentId}
        onCreateConversation={handleNewChat}
        onSwitchConversation={handleSwitchConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      <main
        id="main-content"
        tabIndex={-1}
        aria-label="对话内容"
        className="flex-1 flex flex-col min-w-0"
      >
        <header
          className="h-14 px-6 flex items-center shrink-0 border-b"
          style={{ borderColor: 'var(--border)', background: 'var(--cream)', backdropFilter: 'blur(12px)' }}
        >
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg transition-colors lg:hidden"
              style={{ color: 'var(--ink-muted)' }}
              aria-label={A11Y.MENU}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            </button>
            <h1
              className="text-lg tracking-tight"
              style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--ink)' }}
            >
              InterviewRAG
            </h1>
          </div>
          <div className="flex-1" />
          <ThemeToggle />
        </header>

        <ErrorBoundary>
          <ChatHistory
            messages={currentMessages}
            isLoading={isLoading}
            onSend={handleSend}
            onRegenerate={handleRegenerate}
          />
        </ErrorBoundary>

        <ChatInput onSend={handleSend} isLoading={isLoading} onStop={handleStop} />
      </main>

      <Modal
        open={!!deleteConfirmId}
        onClose={() => setDeleteConfirmId(null)}
        title="删除对话？"
        widthClassName="w-80"
      >
        <p className="text-sm mb-5" style={{ color: 'var(--ink-muted)' }}>
          此操作无法撤销，对话中的所有消息将被永久删除。
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={() => setDeleteConfirmId(null)}
            className="px-4 py-2 text-sm rounded-lg transition-all"
            style={{ border: '1px solid var(--border)', color: 'var(--ink-light)' }}
          >
            取消
          </button>
          <button
            onClick={confirmDelete}
            className="px-4 py-2 text-sm font-medium rounded-lg transition-all"
            style={{ background: 'var(--accent)', color: '#ffffff' }}
          >
            删除
          </button>
        </div>
      </Modal>
    </div>
  )
}
