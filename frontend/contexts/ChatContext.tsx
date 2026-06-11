'use client'

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
} from 'react'
import type { ReactNode } from 'react'
import { queryStream } from '@/lib/api'
import type { Message, SourceRef } from '@/lib/types'

// =====================================================================
// ChatContext: 统一 chat 状态管理
// 包含 conversations state + 流式 partial + localStorage 持久化（单点写入）
// =====================================================================

const STORAGE_KEY = 'interviewrag_conversations'
const ACTIVE_KEY = 'interviewrag_active_id'
const MAX_TITLE_LENGTH = 15
const SAVE_DEBOUNCE_MS = 100

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: number
  updatedAt: number
}

export interface StreamPartial {
  convId: string
  aiMsgId: string
  content: string
  sources: SourceRef[]
}

export interface ChatContextValue {
  // 流式状态
  isLoading: boolean
  streamingConvId: string | null
  partial: StreamPartial | null

  // 流式控制
  sendMessage: (content: string, conversationId: string) => Promise<void>
  subscribe: (cb: (partial: StreamPartial | null) => void) => () => void
  getPartial: () => StreamPartial | null

  // 对话管理
  conversations: Conversation[]
  currentId: string | null
  currentConversation: Conversation | null
  currentMessages: Message[]
  createConversation: () => string
  switchConversation: (id: string) => void
  deleteConversation: (id: string) => void
  updateMessages: (msgs: Message[]) => void
  renameConversation: (id: string, title: string) => void
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider')
  return ctx
}

// ---------- helpers ----------

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function getTitleFromMessages(messages: Message[]): string {
  const firstUserMsg = messages.find((m) => m.role === 'user')
  if (!firstUserMsg) return '新对话'
  const title = firstUserMsg.content.slice(0, MAX_TITLE_LENGTH)
  return title.length < firstUserMsg.content.length ? title + '...' : title
}

function loadConversations(): Conversation[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function loadActiveId(loaded: Conversation[]): string | null {
  if (typeof window === 'undefined') return null
  try {
    const savedActiveId = localStorage.getItem(ACTIVE_KEY)
    if (savedActiveId && loaded.some((c) => c.id === savedActiveId)) {
      return savedActiveId
    }
  } catch {
    // ignore
  }
  return loaded.length > 0 ? loaded[0].id : null
}

function createEmptyConversation(): Conversation {
  return {
    id: generateId(),
    title: '新对话',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}

// =====================================================================
// ChatProvider
// =====================================================================

export function ChatProvider({ children }: { children: ReactNode }) {
  // ---- conversations state ----
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)

  // ---- streaming state ----
  const [isLoading, setIsLoading] = useState(false)
  const [streamingConvId, setStreamingConvId] = useState<string | null>(null)
  const [partial, setPartial] = useState<StreamPartial | null>(null)

  // ---- refs ----
  const abortRef = useRef<AbortController | null>(null)
  const subscribersRef = useRef<Set<(p: StreamPartial | null) => void>>(new Set())
  const partialRef = useRef<StreamPartial | null>(null)
  const currentIdRef = useRef<string | null>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasHydratedRef = useRef(false)

  partialRef.current = partial
  currentIdRef.current = currentId

  // ---- 加载 localStorage（仅一次） ----
  useEffect(() => {
    const loaded = loadConversations()
    setConversations(loaded)
    setCurrentId(loadActiveId(loaded))
    hasHydratedRef.current = true
  }, [])

  // ---- 持久化：单一写入点，debounce 100ms ----
  useEffect(() => {
    if (!hasHydratedRef.current) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
        if (currentId) {
          localStorage.setItem(ACTIVE_KEY, currentId)
        }
      } catch {
        // localStorage full or unavailable
      }
    }, SAVE_DEBOUNCE_MS)
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [conversations, currentId])

  // ---- 流式控制 ----
  const subscribe = useCallback((cb: (p: StreamPartial | null) => void) => {
    subscribersRef.current.add(cb)
    return () => {
      subscribersRef.current.delete(cb)
    }
  }, [])

  const getPartial = useCallback(() => partialRef.current, [])

  /**
   * 把 partial 合并到 conversations[partial.convId].messages
   * - 找到 aiMsgId → 替换 content + sources
   * - 找不到 → append 新 ai message
   * 注意：使用 partial.convId，不依赖 currentId（用户可能流式中途切走）
   */
  const mergePartialIntoConversation = useCallback((p: StreamPartial) => {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== p.convId) return c
        const existingIdx = c.messages.findIndex((m) => m.id === p.aiMsgId)
        if (existingIdx >= 0) {
          const nextMessages = c.messages.map((m) =>
            m.id === p.aiMsgId
              ? { ...m, content: p.content, sources: p.sources }
              : m,
          )
          return { ...c, messages: nextMessages, updatedAt: Date.now() }
        }
        const aiMsg: Message = {
          id: p.aiMsgId,
          role: 'assistant',
          content: p.content,
          sources: p.sources,
          timestamp: Date.now(),
        }
        return { ...c, messages: [...c.messages, aiMsg], updatedAt: Date.now() }
      }),
    )
  }, [])

  const sendMessage = useCallback(
    async (content: string, conversationId: string) => {
      if (!content.trim() || isLoading) return

      // 三步：写 user + 写空 ai + 启流
      const userMsg: Message = {
        id: Date.now().toString(),
        role: 'user',
        content,
        timestamp: Date.now(),
      }
      const aiMsgId = (Date.now() + 1).toString()
      const aiMsg: Message = {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        sources: [],
        timestamp: Date.now(),
      }

      // 1+2: 把 user + 空 ai 一次性写入
      setConversations((prev) => {
        // 若对话不存在，创建之
        const exists = prev.some((c) => c.id === conversationId)
        const next = exists
          ? prev
          : [createEmptyConversationWithId(conversationId), ...prev]
        return next.map((c) => {
          if (c.id !== conversationId) return c
          const isFirstUser = c.messages.length === 0
          return {
            ...c,
            messages: [...c.messages, userMsg, aiMsg],
            updatedAt: Date.now(),
            title: isFirstUser ? getTitleFromMessages([userMsg]) : c.title,
          }
        })
      })

      // 3: 触发 partial
      const initial: StreamPartial = {
        convId: conversationId,
        aiMsgId,
        content: '',
        sources: [],
      }
      setPartial(initial)
      partialRef.current = initial

      setIsLoading(true)
      setStreamingConvId(conversationId)

      abortRef.current = new AbortController()

      let fullContent = ''
      let sources: SourceRef[] = []

      try {
        for await (const event of queryStream(content, conversationId, [], abortRef.current?.signal)) {
          if (event.error) break

          if (event.content) {
            fullContent += event.content
            const updated: StreamPartial = {
              convId: conversationId,
              aiMsgId,
              content: fullContent,
              sources,
            }
            setPartial(updated)
            partialRef.current = updated
            mergePartialIntoConversation(updated)
            subscribersRef.current.forEach((cb) => cb(updated))
          }

          if (event.done) {
            if (event.sources) {
              sources = event.sources
              const updated: StreamPartial = {
                convId: conversationId,
                aiMsgId,
                content: fullContent,
                sources,
              }
              setPartial(updated)
              partialRef.current = updated
              mergePartialIntoConversation(updated)
              subscribersRef.current.forEach((cb) => cb(updated))
            }
          }
        }
      } catch (err) {
        // 区分 abort（用户主动切走）和真实错误
        const isAbort = err instanceof Error && (
          err.name === 'AbortError' ||
          abortRef.current?.signal.aborted
        )
        if (isAbort) {
          // 预期中止：partial 内容已被 mergePartialIntoConversation 增量写入
          // （每次 event.content 都会写回），不需要拼错误信息
          return
        }
        const errMsg = err instanceof Error ? err.message : '未知'
        const errored: StreamPartial = {
          ...(partialRef.current ?? initial),
          content: fullContent + `\n\n[错误: ${errMsg}]`,
        }
        setPartial(errored)
        partialRef.current = errored
        mergePartialIntoConversation(errored)
        subscribersRef.current.forEach((cb) => cb(errored))
      } finally {
        setIsLoading(false)
        setStreamingConvId(null)
      }
    },
    [isLoading, mergePartialIntoConversation],
  )

  // ---- 对话 CRUD ----
  const createConversation = useCallback((): string => {
    const newConv = createEmptyConversation()
    setConversations((prev) => [newConv, ...prev])
    setCurrentId(newConv.id)
    return newConv.id
  }, [])

  const switchConversation = useCallback((id: string) => {
    // 切换对话时中止当前流式请求
    abortRef.current?.abort()
    setCurrentId(id)
  }, [])

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id)
      if (next.length === 0) {
        const newConv = createEmptyConversation()
        setCurrentId(newConv.id)
        return [newConv]
      }
      // 如果删的是当前对话，切到第一个
      if (currentIdRef.current === id) {
        setCurrentId(next[0].id)
      }
      return next
    })
  }, [])

  const updateMessages = useCallback((msgs: Message[]) => {
    const targetId = currentIdRef.current
    if (!targetId) return
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== targetId) return c
        return {
          ...c,
          messages: msgs,
          title: c.title === '新对话' ? getTitleFromMessages(msgs) : c.title,
          updatedAt: Date.now(),
        }
      }),
    )
  }, [])

  const renameConversation = useCallback((id: string, title: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title } : c)),
    )
  }, [])

  // ---- 派生值 ----
  const currentConversation = useMemo(
    () => conversations.find((c) => c.id === currentId) ?? null,
    [conversations, currentId],
  )
  const currentMessages = currentConversation?.messages ?? []

  const value: ChatContextValue = {
    isLoading,
    streamingConvId,
    partial,
    sendMessage,
    subscribe,
    getPartial,
    conversations,
    currentId,
    currentConversation,
    currentMessages,
    createConversation,
    switchConversation,
    deleteConversation,
    updateMessages,
    renameConversation,
  }

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

// 若对话不存在，用给定的 id 创建之（用于 sendMessage 中 race-safe）
function createEmptyConversationWithId(id: string): Conversation {
  return {
    id,
    title: '新对话',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}
