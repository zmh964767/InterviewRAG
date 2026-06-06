'use client'

import { useState, useEffect, useCallback } from 'react'
import { ChatHistory } from '@/components/chat/ChatHistory'
import { ChatInput } from '@/components/chat/ChatInput'
import { Sidebar } from '@/components/layout/Sidebar'
import { useChat } from '@/hooks/useChat'
import { useConversations } from '@/hooks/useConversations'
import { getStats } from '@/lib/api'
import type { StatsResponse } from '@/lib/types'

export default function Home() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const {
    conversations, currentId,
    createConversation, switchConversation, deleteConversation, updateMessages,
  } = useConversations()

  const { messages, isLoading, error, sendMessage: rawSendMessage, clearMessages } = useChat()

  // Sync messages to current conversation for persistence
  useEffect(() => {
    if (currentId && messages.length > 0) {
      updateMessages(messages)
    }
  }, [messages, currentId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Send message: create conversation if needed, then send
  const sendMessage = useCallback((content: string) => {
    if (conversations.length === 0 || !currentId) {
      createConversation()
    }
    rawSendMessage(content)
  }, [conversations.length, currentId, createConversation, rawSendMessage])

  // Clear messages
  const handleClear = useCallback(() => {
    clearMessages()
    if (currentId) {
      updateMessages([])
    }
  }, [clearMessages, currentId, updateMessages])

  // Regenerate last response
  const handleRegenerate = useCallback(() => {
    if (messages.length < 2) return
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')
    if (lastUserMsg) {
      rawSendMessage(lastUserMsg.content)
    }
  }, [messages, rawSendMessage])

  useEffect(() => {
    getStats().then(setStats).catch(() => {})
  }, [])

  return (
    <div className="flex h-screen" style={{ background: 'var(--cream)' }}>
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        stats={stats}
        conversations={conversations}
        currentId={currentId}
        onCreateConversation={createConversation}
        onSwitchConversation={(id) => {
          switchConversation(id)
          clearMessages()
        }}
        onDeleteConversation={deleteConversation}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header
          className="h-14 px-6 flex items-center justify-between shrink-0 border-b"
          style={{ borderColor: 'var(--border)', background: 'rgba(250, 248, 245, 0.8)', backdropFilter: 'blur(12px)' }}
        >
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg transition-colors lg:hidden"
              style={{ color: 'var(--ink-muted)' }}
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
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-all"
              style={{ color: 'var(--ink-muted)', border: '1px solid var(--border)' }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)' }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--ink-muted)' }}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              新对话
            </button>
          )}
        </header>

        <ChatHistory
          messages={messages}
          isLoading={isLoading}
          onSend={sendMessage}
          onRegenerate={handleRegenerate}
        />

        {error && (
          <div
            className="mx-6 mb-3 px-4 py-3 rounded-xl animate-fade-in"
            style={{ background: 'var(--accent-soft)', border: '1px solid var(--accent)' }}
          >
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 shrink-0" style={{ color: 'var(--accent)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm" style={{ color: 'var(--accent)' }}>{error}</p>
            </div>
          </div>
        )}

        <ChatInput onSend={sendMessage} isLoading={isLoading} />
      </div>
    </div>
  )
}
