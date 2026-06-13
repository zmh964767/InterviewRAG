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

export interface ChatError {
  kind: 'aborted' | 'error'
  messageId: string
  message: string
}

export interface ChatContextValue {
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
  const [conversations, dispatch] = useReducer(convReducer, [])
  const conversationsRef = useRef<Conversation[]>([])
  conversationsRef.current = conversations
  const [currentId, setCurrentId] = useState<string | null>(null)

  // ---- streaming state ----
  const [isLoading, setIsLoading] = useState(false)
  const [streamingConvId, setStreamingConvId] = useState<string | null>(null)
  const [partial, setPartial] = useState<StreamPartial | null>(null)
  const [lastError, setLastError] = useState<ChatError | null>(null)

  // ---- refs ----
  const abortRef = useRef<AbortController | null>(null)
  // 用户主动中止标记：手动点停止时置 true，
  // sendMessage 的 finally 据此决定是否显示 InlineErrorBanner。
  // 手动点停止 = 显示"重新生成"banner（用户留在当前对话，想重试）。
  // 切会话 = 不触发 abort（旧流后台继续生成）。
  const userStopRef = useRef(false)
  const subscribersRef = useRef<Set<(p: StreamPartial | null) => void>>(
    new Set(),
  )
  const partialRef = useRef<StreamPartial | null>(null)
  const currentIdRef = useRef<string | null>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasHydratedRef = useRef(false)
  const isLoadingRef = useRef(false)
  isLoadingRef.current = isLoading

  partialRef.current = partial
  currentIdRef.current = currentId

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

  // ---- 流式控制 ----
  const subscribe = useCallback((cb: (p: StreamPartial | null) => void) => {
    subscribersRef.current.add(cb)
    return () => {
      subscribersRef.current.delete(cb)
    }
  }, [])

  const getPartial = useCallback(() => partialRef.current, [])

  const sendMessage = useCallback(
    async (content: string, conversationId: string, options?: { existingAiMsgId?: string; skipUser?: boolean }) => {
      if (!content.trim() || isLoadingRef.current) return

      const { existingAiMsgId, skipUser } = options ?? {}

      const aiMsgId = existingAiMsgId ?? (Date.now() + 1).toString()

      // existingAiMsgId 路径：continueLast 已清空 ai 消息，sendMessage 复用同一条消息
      // skipUser=true 时不追加 user 消息（continueLast 场景已有 user 消息）
      // fullContent 从空开始，新流的 token 直接写入
      let existingContent = ''

      if (existingAiMsgId) {
        // continueLast: 不清空 ai 消息（保留已有 partial），不追加 user 消息
        // 新流的 token 会追加到 existingContent 后面
        if (skipUser) {
          // continueLast: 不追加 user 消息，不修改已有 ai 消息
          // 调用方（continueLast）已清空 ai 消息内容，此处 existingContent 从空开始
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
            }
            dispatch({ type: 'UPDATE_MESSAGES', payload: { convId: conversationId, messages: [...conv.messages, userMsg] } })
          }
        }
      } else {
        // 正常发送：创建新的 user + ai 消息对
        const userMsg: Message = {
          id: Date.now().toString(),
          role: 'user',
          content,
          timestamp: Date.now(),
        }
        const aiMsg: Message = {
          id: aiMsgId,
          role: 'assistant',
          content: '',
          sources: [],
          timestamp: Date.now(),
        }
        const existingConv = conversationsRef.current.find(c => c.id === conversationId)
        if (!existingConv) {
          dispatch({ type: 'CREATE', payload: createEmptyConversationWithId(conversationId) })
        }
        const isFirstUser = !existingConv || existingConv.messages.length === 0
        dispatch({
          type: 'APPEND_USER_AI',
          payload: { convId: conversationId, userMsg, aiMsg, isFirstUser }
        })
      }

      // 3: 触发 partial（continue 时从已有内容开始）
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
        for await (const event of queryStream(
          content,
          conversationId,
          [],
          controller.signal,
        )) {
          // 中断检查：用局部 controller，不读 ref（ref 可能已被下一轮 sendMessage 覆盖）。
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
              dispatch({ type: 'REPLACE_MESSAGE', payload: { convId: updated.convId, aiMsgId: updated.aiMsgId, content: updated.content, sources: updated.sources } })
              subscribersRef.current.forEach((cb) => cb(updated))
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
        // ★ 仅当 controller 仍是当前活跃的才清状态。
        //   若用户已切走并开始了新流，旧流的 finally 不应覆盖新流的 isLoading/streamingConvId。
        if (abortRef.current === controller) {
          setIsLoading(false)
          setStreamingConvId(null)
        }
      }
    },
    [],
  )

  // ---- 流式控制:手动中止（用户点了 Stop 按钮，显示"重新生成"banner） ----
  const abort = useCallback(() => {
    userStopRef.current = true
    if (abortRef.current) {
      abortRef.current.abort()
    }
  }, [])

  // ---- 流式控制:重新生成（清空旧 partial + 用同一个 aiMsgId 重新生成） ----
  // 后端不支持"从断点续写"，所以 continueLast = 清空已有 partial + 重新生成。
  // 传 existingAiMsgId 让 sendMessage 更新已有 ai 消息（不创建新的消息对），
  // 避免对话里出现重复的 user 消息。

  const continueLast = useCallback(async () => {
    const targetConvId = currentIdRef.current
    if (!targetConvId) return
    const conv = conversationsRef.current.find((c) => c.id === targetConvId)
    if (!conv) return
    const lastAssistant = [...conv.messages].reverse().find((m) => m.role === 'assistant')
    const lastUser = [...conv.messages].reverse().find((m) => m.role === 'user')
    if (!lastUser) return
    // 清空已有 partial 内容，用同一个 aiMsgId 重新生成（不创建重复 user 消息）
    if (lastAssistant) {
      dispatch({
        type: 'REPLACE_MESSAGE',
        payload: { convId: targetConvId, aiMsgId: lastAssistant.id, content: '', sources: [] }
      })
      // 同步清空 partial ref（dispatch 是异步的，sendMessage 会读 partialRef/content）
      const cleared: StreamPartial = { convId: targetConvId, aiMsgId: lastAssistant.id, content: '', sources: [] }
      setPartial(cleared)
      partialRef.current = cleared
    }
    await sendMessage(lastUser.content, targetConvId, {
      existingAiMsgId: lastAssistant?.id,
      skipUser: true,
    })
  }, [sendMessage])

  // streamingConvIdRef for deleteConversation
  const streamingConvIdRef = useRef<string | null>(null)
  streamingConvIdRef.current = streamingConvId

  // ---- 清除错误(InlineErrorBanner 的"关闭"按钮调用) ----
  const clearError = useCallback((messageId?: string) => {
    setLastError((prev) => {
      if (!prev) return prev
      if (messageId && prev.messageId !== messageId) return prev
      return null
    })
  }, [])

  // ---- 对话 CRUD ----
  const createConversation = useCallback((): string => {
    const newConv = createEmptyConversation()
    dispatch({ type: 'CREATE', payload: newConv })
    setCurrentId(newConv.id)
    return newConv.id
  }, [])

  const switchConversation = useCallback((id: string) => {
    // 不中止当前流：让流在后台继续生成，partial 内容会通过
    // dispatch REPLACE_MESSAGE 增量写入对应会话。切回时直接从
    // conversations 里读取最新状态，不打断用户体验。
    setCurrentId(id)
  }, [])

  const deleteConversation = useCallback((id: string) => {
    // 如果删的是当前正在流的对话,先 abort
    if (streamingConvIdRef.current === id && abortRef.current) {
      abortRef.current.abort()
    }
    const remaining = conversationsRef.current.filter(c => c.id !== id)
    dispatch({ type: 'DELETE', payload: { id } })
    if (remaining.length === 0) {
      const newConv = createEmptyConversation()
      dispatch({ type: 'CREATE', payload: newConv })
      setCurrentId(newConv.id)
    } else if (currentIdRef.current === id) {
      setCurrentId(remaining[0].id)
    }
  }, [])

  const updateMessages = useCallback((msgs: Message[]) => {
    const targetId = currentIdRef.current
    if (!targetId) return
    const conv = conversationsRef.current.find(c => c.id === targetId)
    const title = conv?.title === '新对话' ? getTitleFromMessages(msgs) : undefined
    dispatch({ type: 'UPDATE_MESSAGES', payload: { convId: targetId, messages: msgs, title } })
  }, [])

  const renameConversation = useCallback((id: string, title: string) => {
    dispatch({ type: 'RENAME', payload: { id, title } })
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
    lastError,
    sendMessage,
    abort,
    continueLast,
    clearError,
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
