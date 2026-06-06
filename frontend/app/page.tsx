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
    conversations, currentId, messages,
    createConversation, switchConversation, deleteConversation, updateMessages,
  } = useConversations()

  const { isLoading, error, sendMessage: rawSendMessage, clearMessages } = useChat()

  // Sync messages from useChat to useConversations
  const sendMessage = useCallback((content: string) => {
    if (conversations.length === 0 || !currentId) {
      createConversation()
    }
    rawSendMessage(content)
  }, [conversations.length, currentId, createConversation, rawSendMessage])

  // After AI responds, save messages to current conversation
  useEffect(() => {
    if (messages.length > 0 && currentId) {
      updateMessages(messages)
    }
  }, [messages, currentId, updateMessages])

  // Clear messages should also clear the current conversation
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
      // Remove last AI message and resend
      const newMessages = messages.slice(0, -1)
      updateMessages(newMessages)
      rawSendMessage(lastUserMsg.content)
    }
  }, [messages, updateMessages, rawSendMessage])

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
          const conv = conversations.find((c) => c.id === id)
          if (conv) {
            // Load conversation messages into useChat
            clearMessages()
            // We need to set messages directly - this is a limitation
            // For now, switching conversations will show empty until we send a message
          }
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
