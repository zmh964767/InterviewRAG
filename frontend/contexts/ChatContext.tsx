'use client'

import {
  createContext,
  useContext,
  useState,
  useReducer,
  useCallback,
  useRef,
  useEffect,
  useMemo,
} from 'react'
import type { Dispatch, ReactNode } from 'react'
import { queryStream } from '@/lib/api'
import type { Message, SourceRef } from '@/lib/types'

// =====================================================================
// ChatContext: 统一 chat 状态管理
// 拆分为两个 Context 以减少高频流式期间的非必要重渲染：
//   - ChatConversationsContext: 会话列表 + CRUD 回调
//   - ChatStreamingContext: 流式状态 + sendMessage/abort/...
// 通过 useChatContext 组合订阅（向后兼容）。
//
// 跨 Provider 共享的 mutable 状态（abortRef / streamingConvIdRef）保留在
// ChatProvider 顶层,通过 props 下传，避免 Provider 之间互传回调。
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

export interface ChatError {
  kind: 'aborted' | 'error'
  messageId: string
  message: string
}

export interface ChatConversationsContextValue {
  // 派生
  conversations: Conversation[]
  currentId: string | null
  currentConversation: Conversation | null
  currentMessages: Message[]

  // CRUD
  createConversation: () => string
  switchConversation: (id: string) => void
  deleteConversation: (id: string) => void
  updateMessages: (msgs: Message[]) => void
  renameConversation: (id: string, title: string) => void
}

export interface ChatStreamingContextValue {
  // 流式状态
  isLoading: boolean
  streamingConvId: string | null
  partial: StreamPartial | null
  lastError: ChatError | null

  // 流式控制
  sendMessage: (content: string, conversationId: string, options?: { existingAiMsgId?: string; skipUser?: boolean }) => Promise<void>
  abort: () => void
  continueLast: () => Promise<void>
  clearError: (messageId?: string) => void
}

// 向后兼容：完整接口 = 两个子 context 的并集
export type ChatContextValue = ChatConversationsContextValue & ChatStreamingContextValue

const ChatConversationsContext = createContext<ChatConversationsContextValue | null>(null)
const ChatStreamingContext = createContext<ChatStreamingContextValue | null>(null)

// 兼容旧引用
const ChatContext = ChatConversationsContext

type ConvAction =
  | { type: 'LOAD'; payload: Conversation[] }
  | { type: 'CREATE'; payload: Conversation }
  | { type: 'DELETE'; payload: { id: string } }
  | { type: 'RENAME'; payload: { id: string; title: string } }
  | { type: 'REPLACE_MESSAGE'; payload: { convId: string; aiMsgId: string; content: string; sources: SourceRef[] } }
  | { type: 'UPDATE_MESSAGES'; payload: { convId: string; messages: Message[]; title?: string } }
  | { type: 'APPEND_USER_AI'; payload: { convId: string; userMsg: Message; aiMsg: Message; isFirstUser: boolean } }
  | { type: 'TOUCH'; payload: { id: string } }

function convReducer(state: Conversation[], action: ConvAction): Conversation[] {
  switch (action.type) {
    case 'LOAD':
      return action.payload
    case 'CREATE':
      return [action.payload, ...state]
    case 'DELETE':
      return state.filter(c => c.id !== action.payload.id)
    case 'RENAME':
      return state.map(c => c.id === action.payload.id ? { ...c, title: action.payload.title } : c)
    case 'REPLACE_MESSAGE': {
      const { convId, aiMsgId, content, sources } = action.payload
      return state.map(c => {
        if (c.id !== convId) return c
        const idx = c.messages.findIndex(m => m.id === aiMsgId)
        if (idx >= 0) {
          const next = c.messages.slice()
          next[idx] = { ...next[idx], content, sources }
          return { ...c, messages: next, updatedAt: Date.now() }
        }
        const newMsg: Message = { id: aiMsgId, role: 'assistant', content, sources, timestamp: Date.now(), conversationId: convId }
        return { ...c, messages: [...c.messages, newMsg], updatedAt: Date.now() }
      })
    }
    case 'UPDATE_MESSAGES': {
      const { convId, messages, title } = action.payload
      return state.map(c => {
        if (c.id !== convId) return c
        return { ...c, messages, title: title ?? c.title, updatedAt: Date.now() }
      })
    }
    case 'APPEND_USER_AI': {
      const { convId, userMsg, aiMsg, isFirstUser } = action.payload
      return state.map(c => {
        if (c.id !== convId) return c
        return {
          ...c,
          messages: [...c.messages, userMsg, aiMsg],
          updatedAt: Date.now(),
          title: isFirstUser ? getTitleFromMessages([userMsg]) : c.title,
        }
      })
    }
    case 'TOUCH':
      return state.map(c => c.id === action.payload.id ? { ...c, updatedAt: Date.now() } : c)
    default:
      return state
  }
}

// ---------- hooks ----------

export function useChatConversationsContext(): ChatConversationsContextValue {
  const ctx = useContext(ChatConversationsContext)
  if (!ctx) throw new Error('useChatConversationsContext must be used within ChatProvider')
  return ctx
}

export function useChatStreamingContext(): ChatStreamingContextValue {
  const ctx = useContext(ChatStreamingContext)
  if (!ctx) throw new Error('useChatStreamingContext must be used within ChatProvider')
  return ctx
}

// 向后兼容：组合两个 context
export function useChatContext(): ChatContextValue {
  const conv = useChatConversationsContext()
  const stream = useChatStreamingContext()
  return { ...conv, ...stream }
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

function createEmptyConversationWithId(id: string): Conversation {
  return {
    id,
    title: '新对话',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}

// =====================================================================
// Inner Provider 共享 props：reducer state + 顶层 refs
// 顶层持有 abortRef / streamingConvIdRef（跨 Provider mutable 状态）
// =====================================================================

interface SharedChatState {
  conversations: Conversation[]
  dispatch: Dispatch<ConvAction>
  currentId: string | null
  setCurrentId: (id: string | null) => void
  conversationsRef: React.MutableRefObject<Conversation[]>
  currentIdRef: React.MutableRefObject<string | null>
  justCreatedIdRef: React.MutableRefObject<string | null>
  abortRef: React.MutableRefObject<AbortController | null>
  streamingConvIdRef: React.MutableRefObject<string | null>
}

// ---------------------------------------------------------------------
// InnerConversationsProvider
// ---------------------------------------------------------------------

function InnerConversationsProvider({
  state,
  children,
}: {
  state: SharedChatState
  children: ReactNode
}) {
  const {
    conversations,
    dispatch,
    currentId,
    setCurrentId,
    conversationsRef,
    currentIdRef,
    justCreatedIdRef,
    abortRef,
    streamingConvIdRef,
  } = state

  const createConversation = useCallback((): string => {
    const newConv = createEmptyConversation()
    dispatch({ type: 'CREATE', payload: newConv })
    setCurrentId(newConv.id)
    justCreatedIdRef.current = newConv.id
    return newConv.id
  }, [dispatch, setCurrentId, justCreatedIdRef])

  const switchConversation = useCallback((id: string) => {
    setCurrentId(id)
  }, [setCurrentId])

  const deleteConversation = useCallback((id: string) => {
    // 删的是当前正在流的对话,先 abort
    if (streamingConvIdRef.current === id && abortRef.current) {
      abortRef.current.abort()
    }
    const remaining = conversationsRef.current.filter(c => c.id !== id)
    dispatch({ type: 'DELETE', payload: { id } })
    if (remaining.length === 0) {
      const newConv = createEmptyConversation()
      dispatch({ type: 'CREATE', payload: newConv })
      setCurrentId(newConv.id)
      justCreatedIdRef.current = newConv.id
    } else if (currentIdRef.current === id) {
      setCurrentId(remaining[0].id)
    }
  }, [dispatch, setCurrentId, conversationsRef, currentIdRef, justCreatedIdRef, abortRef, streamingConvIdRef])

  const updateMessages = useCallback((msgs: Message[]) => {
    const targetId = currentIdRef.current
    if (!targetId) return
    const conv = conversationsRef.current.find(c => c.id === targetId)
    const title = conv?.title === '新对话' ? getTitleFromMessages(msgs) : undefined
    dispatch({ type: 'UPDATE_MESSAGES', payload: { convId: targetId, messages: msgs, title } })
  }, [dispatch, conversationsRef, currentIdRef])

  const renameConversation = useCallback((id: string, title: string) => {
    dispatch({ type: 'RENAME', payload: { id, title } })
  }, [dispatch])

  const currentConversation = useMemo(
    () => conversations.find((c) => c.id === currentId) ?? null,
    [conversations, currentId],
  )
  const currentMessages = useMemo(
    () => currentConversation?.messages ?? [],
    [currentConversation],
  )

  const value = useMemo<ChatConversationsContextValue>(
    () => ({
      conversations,
      currentId,
      currentConversation,
      currentMessages,
      createConversation,
      switchConversation,
      deleteConversation,
      updateMessages,
      renameConversation,
    }),
    [
      conversations,
      currentId,
      currentConversation,
      currentMessages,
      createConversation,
      switchConversation,
      deleteConversation,
      updateMessages,
      renameConversation,
    ],
  )

  return <ChatConversationsContext.Provider value={value}>{children}</ChatConversationsContext.Provider>
}

// ---------------------------------------------------------------------
// InnerStreamingProvider
// ---------------------------------------------------------------------

function InnerStreamingProvider({
  state,
  children,
}: {
  state: SharedChatState
  children: ReactNode
}) {
  const {
    conversations,
    dispatch,
    conversationsRef,
    currentIdRef,
    justCreatedIdRef,
    abortRef,
  } = state

  // ---- streaming state ----
  const [isLoading, setIsLoading] = useState(false)
  const [streamingConvId, setStreamingConvId] = useState<string | null>(null)
  const [partial, setPartial] = useState<StreamPartial | null>(null)
  const [lastError, setLastError] = useState<ChatError | null>(null)

  // ---- 局部 refs ----
  const userStopRef = useRef(false)
  const partialRef = useRef<StreamPartial | null>(null)
  const isLoadingRef = useRef(false)
  isLoadingRef.current = isLoading
  partialRef.current = partial
  // streamingConvId 同步到顶层 ref (供 deleteConversation 判断)
  state.streamingConvIdRef.current = streamingConvId

  const sendMessage = useCallback(
    async (content: string, conversationId: string, options?: { existingAiMsgId?: string; skipUser?: boolean }) => {
      if (!content.trim() || isLoadingRef.current) return

      const { existingAiMsgId, skipUser } = options ?? {}

      const aiMsgId = existingAiMsgId ?? (Date.now() + 1).toString()

      let existingContent = ''

      if (existingAiMsgId) {
        if (skipUser) {
          existingContent = ''
          dispatch({ type: 'TOUCH', payload: { id: conversationId } })
        } else {
          const conv = conversationsRef.current.find(c => c.id === conversationId)
          const existing = conv?.messages.find(m => m.id === existingAiMsgId)
          existingContent = existing?.content ?? ''
          if (conv) {
            const userMsg: Message = {
              id: Date.now().toString(),
              role: 'user',
              content,
              timestamp: Date.now(),
              conversationId,
            }
            dispatch({ type: 'UPDATE_MESSAGES', payload: { convId: conversationId, messages: [...conv.messages, userMsg] } })
          }
        }
      } else {
        const userMsg: Message = {
          id: Date.now().toString(),
          role: 'user',
          content,
          timestamp: Date.now(),
          conversationId,
        }
        const aiMsg: Message = {
          id: aiMsgId,
          role: 'assistant',
          content: '',
          sources: [],
          timestamp: Date.now(),
          conversationId,
        }
        const existingConv = conversationsRef.current.find(c => c.id === conversationId)
        if (!existingConv && justCreatedIdRef.current !== conversationId) {
          dispatch({ type: 'CREATE', payload: createEmptyConversationWithId(conversationId) })
        }
        const isFirstUser = !existingConv || existingConv.messages.length === 0
        if (justCreatedIdRef.current === conversationId) {
          justCreatedIdRef.current = null
        }
        dispatch({
          type: 'APPEND_USER_AI',
          payload: { convId: conversationId, userMsg, aiMsg, isFirstUser }
        })
      }

      const initial: StreamPartial = {
        convId: conversationId,
        aiMsgId,
        content: existingContent,
        sources: [],
      }
      setPartial(initial)
      partialRef.current = initial
      setLastError(null)

      setIsLoading(true)
      setStreamingConvId(conversationId)

      const controller = new AbortController()
      abortRef.current = controller

      let fullContent = existingContent
      let sources: SourceRef[] = []

      try {
        const conv = conversationsRef.current.find(c => c.id === conversationId)
        const history = conv?.messages?.slice(-20) || []
        for await (const event of queryStream(
          content,
          conversationId,
          history,
          controller.signal,
        )) {
          if (controller.signal.aborted) {
            if (userStopRef.current) {
              setLastError({ kind: 'aborted', messageId: aiMsgId, message: '' })
            }
            return
          }
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
            dispatch({ type: 'REPLACE_MESSAGE', payload: { convId: updated.convId, aiMsgId: updated.aiMsgId, content: updated.content, sources: updated.sources } })
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
              dispatch({ type: 'REPLACE_MESSAGE', payload: { convId: updated.convId, aiMsgId: updated.aiMsgId, content: updated.content, sources: updated.sources } })
            }
          }
        }
      } catch (err) {
        const isAbort =
          err instanceof Error &&
          (err.name === 'AbortError' || controller.signal.aborted)
        if (isAbort) {
          if (userStopRef.current) {
            setLastError({ kind: 'aborted', messageId: aiMsgId, message: '' })
          }
          return
        }
        const errMsg = err instanceof Error ? err.message : '未知错误'
        setLastError({ kind: 'error', messageId: aiMsgId, message: errMsg })
      } finally {
        userStopRef.current = false
        if (abortRef.current === controller) {
          setIsLoading(false)
          setStreamingConvId(null)
        }
      }
    },
    [dispatch, conversationsRef, justCreatedIdRef, abortRef],
  )

  const abort = useCallback(() => {
    userStopRef.current = true
    if (abortRef.current) {
      abortRef.current.abort()
    }
  }, [abortRef])

  const continueLast = useCallback(async () => {
    const targetConvId = currentIdRef.current
    if (!targetConvId) return
    const conv = conversationsRef.current.find((c) => c.id === targetConvId)
    if (!conv) return
    const lastAssistant = [...conv.messages].reverse().find((m) => m.role === 'assistant')
    const lastUser = [...conv.messages].reverse().find((m) => m.role === 'user')
    if (!lastUser) return
    if (lastAssistant) {
      dispatch({
        type: 'REPLACE_MESSAGE',
        payload: { convId: targetConvId, aiMsgId: lastAssistant.id, content: '', sources: [] }
      })
      const cleared: StreamPartial = { convId: targetConvId, aiMsgId: lastAssistant.id, content: '', sources: [] }
      setPartial(cleared)
      partialRef.current = cleared
    }
    await sendMessage(lastUser.content, targetConvId, {
      existingAiMsgId: lastAssistant?.id,
      skipUser: true,
    })
  }, [sendMessage, conversationsRef, currentIdRef, dispatch])

  const clearError = useCallback((messageId?: string) => {
    setLastError((prev) => {
      if (!prev) return prev
      if (messageId && prev.messageId !== messageId) return prev
      return null
    })
  }, [])

  // Abort in-flight SSE request on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [abortRef])

  const value = useMemo<ChatStreamingContextValue>(
    () => ({
      isLoading,
      streamingConvId,
      partial,
      lastError,
      sendMessage,
      abort,
      continueLast,
      clearError,
    }),
    [isLoading, streamingConvId, partial, lastError, sendMessage, abort, continueLast, clearError],
  )

  return <ChatStreamingContext.Provider value={value}>{children}</ChatStreamingContext.Provider>
}

// =====================================================================
// ChatProvider: 顶层 Provider
// - 持有共享 reducer state (conversations, dispatch) + currentId
// - 持有跨 Provider 共享的 refs (conversationsRef, currentIdRef,
//   justCreatedIdRef, abortRef, streamingConvIdRef)
// - 持有 localStorage 加载 + 持久化 effect
// - 包内层两个子 Provider
// =====================================================================

export function ChatProvider({ children }: { children: ReactNode }) {
  // ---- 共享 state ----
  const [conversations, dispatch] = useReducer(convReducer, [])
  const [currentId, setCurrentId] = useState<string | null>(null)

  // ---- 共享 refs ----
  const conversationsRef = useRef<Conversation[]>([])
  conversationsRef.current = conversations
  const currentIdRef = useRef<string | null>(null)
  currentIdRef.current = currentId
  const justCreatedIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const streamingConvIdRef = useRef<string | null>(null)
  const hasHydratedRef = useRef(false)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ---- 加载 localStorage（仅一次） ----
  useEffect(() => {
    const loaded = loadConversations()
    dispatch({ type: 'LOAD', payload: loaded })
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

  const state: SharedChatState = {
    conversations,
    dispatch,
    currentId,
    setCurrentId,
    conversationsRef,
    currentIdRef,
    justCreatedIdRef,
    abortRef,
    streamingConvIdRef,
  }

  return (
    <InnerConversationsProvider state={state}>
      <InnerStreamingProvider state={state}>
        {children}
      </InnerStreamingProvider>
    </InnerConversationsProvider>
  )
}
