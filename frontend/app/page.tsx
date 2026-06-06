'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
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
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  // 用 ref 追踪是否正在切换对话，避免循环
  const switchingRef = useRef(false)

  const {
    conversations, currentId,
    createConversation, switchConversation, deleteConversation, updateMessages,
  } = useConversations()

  const { messages, isLoading, error, sendMessage: rawSendMessage, clearMessages, loadMessages } = useChat()

  // 持久化：消息变化时保存（防抖）
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (switchingRef.current || !currentId || messages.length === 0) return
    // 防抖：停止更新 500ms 后保存，避免流式过程中频繁写入
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      updateMessages(messages)
    }, 500)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [messages, currentId]) // eslint-disable-line react-hooks/exhaustive-deps

  // 发送消息
  const sendMessage = useCallback((content: string) => {
    if (conversations.length === 0 || !currentId) {
      createConversation()
    }
    rawSendMessage(content)
  }, [conversations.length, currentId, createConversation, rawSendMessage])

  // 新建对话
  const handleNewChat = useCallback(() => {
    createConversation()
    clearMessages()
    // 无需重置
  }, [createConversation, clearMessages])

  // 切换对话：先保存当前消息，再加载历史
  const handleSwitchConversation = useCallback((id: string) => {
    // 先保存当前对话的消息（不等防抖）
    if (currentId && messages.length > 0) {
      updateMessages(messages)
    }
    switchingRef.current = true
    switchConversation(id)
    const conv = conversations.find((c) => c.id === id)
    if (conv) {
      loadMessages(conv.messages)
    } else {
      clearMessages()
    }
    // 下一帧解除切换标记
    requestAnimationFrame(() => { switchingRef.current = false })
  }, [conversations, currentId, messages, switchConversation, loadMessages, clearMessages, updateMessages])

  // 重新生成
  const handleRegenerate = useCallback(() => {
    if (messages.length < 2) return
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')
    if (lastUserMsg) {
      // 无需重置
      rawSendMessage(lastUserMsg.content)
    }
  }, [messages, rawSendMessage])

  // 删除对话
  const handleDeleteConversation = useCallback((id: string) => {
    setDeleteConfirmId(id)
  }, [])

  const confirmDelete = useCallback(() => {
    if (deleteConfirmId) {
      deleteConversation(deleteConfirmId)
      setDeleteConfirmId(null)
    }
  }, [deleteConfirmId, deleteConversation])

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
        onCreateConversation={handleNewChat}
        onSwitchConversation={handleSwitchConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <header
          className="h-14 px-6 flex items-center shrink-0 border-b"
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

      {/* 删除确认弹窗 */}
      {deleteConfirmId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(26, 22, 18, 0.3)', backdropFilter: 'blur(4px)' }}
          onClick={() => setDeleteConfirmId(null)}
        >
          <div
            className="w-80 p-6 rounded-2xl animate-slide-up"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-lg)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold mb-2" style={{ fontFamily: 'var(--font-display)', color: 'var(--ink)' }}>
              删除对话？
            </h3>
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
                style={{ background: 'var(--accent)', color: 'var(--cream)' }}
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
