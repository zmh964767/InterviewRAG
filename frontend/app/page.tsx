'use client'

import { useState, useEffect, useCallback, useRef, useSyncExternalStore } from 'react'
import { ChatHistory } from '@/components/chat/ChatHistory'
import { ChatInput } from '@/components/chat/ChatInput'
import { Sidebar } from '@/components/layout/Sidebar'
import { useChatContext } from '@/contexts/ChatContext'
import { useConversations } from '@/hooks/useConversations'
import { getStats } from '@/lib/api'
import type { StatsResponse, Message } from '@/lib/types'

export default function Home() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  // 每个对话的消息存储
  const messagesMapRef = useRef<Record<string, Message[]>>({})
  // 当前显示的消息（从 Map 中读取）
  const [displayMessages, setDisplayMessages] = useState<Message[]>([])

  const {
    conversations, currentId,
    createConversation, switchConversation, deleteConversation, updateMessages,
  } = useConversations()

  // 从 ChatContext 获取流式状态（跨路由存活）
  const { isLoading, sendMessage, subscribe, getPartial } = useChatContext()

  // 订阅流式 partial 变化（layout 里的 ChatProvider 会通知）
  useEffect(() => {
    const unsubscribe = subscribe((partial) => {
      if (!partial) return
      // 流式进行中，把 partial 写入 messagesMapRef
      const msgs = messagesMapRef.current[partial.convId] || []
      const existing = msgs.find((m) => m.id === partial.aiMsgId)
      let next: Message[]
      if (existing) {
        next = msgs.map((m) =>
          m.id === partial.aiMsgId
            ? { ...m, content: partial.content, sources: partial.sources }
            : m,
        )
      } else {
        next = [
          ...msgs,
          {
            id: partial.aiMsgId,
            role: 'assistant' as const,
            content: partial.content,
            sources: partial.sources,
            timestamp: Date.now(),
          },
        ]
      }
      messagesMapRef.current[partial.convId] = next
      if (partial.convId === currentIdRef.current) {
        setDisplayMessages(next)
      }
    })
    return unsubscribe
  }, [subscribe])

  // 初始化时从 localStorage 恢复消息
  useEffect(() => {
    for (const conv of conversations) {
      if (!messagesMapRef.current[conv.id] && conv.messages.length > 0) {
        messagesMapRef.current[conv.id] = conv.messages
      }
    }
    if (currentId) {
      setDisplayMessages(messagesMapRef.current[currentId] || [])
    }
  }, [conversations, currentId])

  // 卸载时立即持久化
  useEffect(() => {
    return () => {
      if (currentIdRef.current && messagesMapRef.current[currentIdRef.current]) {
        updateMessages(messagesMapRef.current[currentIdRef.current])
      }
    }
  }, [updateMessages])

  // 每个 chunk 立即持久化（去 debounce）
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (currentIdRef.current && displayMessages.length > 0) {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        const latest = messagesMapRef.current[currentIdRef.current!]
        if (latest) updateMessages(latest)
      }, 100)
    }
  }, [displayMessages, updateMessages])

  const currentIdRef = useRef<string | null>(null)
  currentIdRef.current = currentId

  // 发送消息
  const handleSend = useCallback((content: string) => {
    let convId = currentId
    if (!convId || conversations.length === 0) {
      convId = createConversation()
    }
    if (convId) {
      // 把 user message 立即写入 messagesMapRef
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content,
        timestamp: Date.now(),
      }
      const aiMsgId = (Date.now() + 1).toString()
      const newMessages: Message[] = [
        ...(messagesMapRef.current[convId] || []),
        userMessage,
        {
          id: aiMsgId,
          role: 'assistant',
          content: '',
          sources: [],
          timestamp: Date.now(),
        },
      ]
      messagesMapRef.current[convId] = newMessages
      if (convId === currentIdRef.current) {
        setDisplayMessages(newMessages)
      }
      updateMessages(newMessages)
      sendMessage(content, convId)
    }
  }, [currentId, conversations.length, createConversation, sendMessage, updateMessages])

  // 新建对话
  const handleNewChat = useCallback(() => {
    createConversation()
  }, [createConversation])

  // 切换对话
  const handleSwitchConversation = useCallback((id: string) => {
    if (currentId && messagesMapRef.current[currentId]?.length > 0) {
      updateMessages(messagesMapRef.current[currentId])
    }
    switchConversation(id)
    setDisplayMessages(messagesMapRef.current[id] || [])
  }, [currentId, switchConversation, updateMessages])

  // 重新生成
  const handleRegenerate = useCallback(() => {
    if (displayMessages.length < 2 || !currentId) return
    const lastUserMsg = [...displayMessages].reverse().find((m) => m.role === 'user')
    if (lastUserMsg) {
      handleSend(lastUserMsg.content)
    }
  }, [displayMessages, currentId, handleSend])

  // 删除对话
  const handleDeleteConversation = useCallback((id: string) => {
    setDeleteConfirmId(id)
  }, [])

  const confirmDelete = useCallback(() => {
    if (deleteConfirmId) {
      deleteConversation(deleteConfirmId)
      delete messagesMapRef.current[deleteConfirmId]
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
          messages={displayMessages}
          isLoading={isLoading}
          onSend={handleSend}
          onRegenerate={handleRegenerate}
        />

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>

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
