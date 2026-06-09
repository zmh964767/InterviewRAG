'use client'

import { createContext, useContext, useState, useCallback, useRef } from 'react'
import type { ReactNode } from 'react'
import { queryStream } from '@/lib/api'
import type { SourceRef } from '@/lib/types'

// =====================================================================
// ChatContext: 流式状态提升到 layout，路由切换不丢失
// 让 useChat 在 layout 渲染一次，跨路由存活
// =====================================================================

export interface ChatState {
  isLoading: boolean
  streamingConvId: string | null
  partial: { convId: string; aiMsgId: string; content: string; sources: SourceRef[] } | null
}

export interface ChatContextValue {
  isLoading: boolean
  streamingConvId: string | null
  partial: ChatState['partial']
  sendMessage: (content: string, conversationId: string) => Promise<void>
  subscribe: (cb: (partial: ChatState['partial']) => void) => () => void
  getPartial: () => ChatState['partial']
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider')
  return ctx
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(false)
  const [streamingConvId, setStreamingConvId] = useState<string | null>(null)
  const [partial, setPartial] = useState<ChatState['partial']>(null)
  const abortRef = useRef<AbortController | null>(null)
  const subscribersRef = useRef<Set<(p: ChatState['partial']) => void>>(new Set())
  const partialRef = useRef<ChatState['partial']>(null)
  partialRef.current = partial

  const subscribe = useCallback((cb: (p: ChatState['partial']) => void) => {
    subscribersRef.current.add(cb)
    return () => {
      subscribersRef.current.delete(cb)
    }
  }, [])

  const getPartial = useCallback(() => partialRef.current, [])

  const sendMessage = useCallback(
    async (content: string, conversationId: string) => {
      if (!content.trim() || isLoading) return

      setIsLoading(true)
      setStreamingConvId(conversationId)
      const aiMsgId = (Date.now() + 1).toString()
      const initial: ChatState['partial'] = {
        convId: conversationId,
        aiMsgId,
        content: '',
        sources: [],
      }
      setPartial(initial)
      partialRef.current = initial

      abortRef.current = new AbortController()

      let fullContent = ''
      let sources: SourceRef[] = []

      try {
        for await (const event of queryStream(content, conversationId, [])) {
          if (event.error) break

          if (event.content) {
            fullContent += event.content
            const updated: ChatState['partial'] = {
              convId: conversationId,
              aiMsgId,
              content: fullContent,
              sources,
            }
            setPartial(updated)
            partialRef.current = updated
            subscribersRef.current.forEach((cb) => cb(updated))
          }

          if (event.done) {
            if (event.sources) {
              sources = event.sources
              const updated: ChatState['partial'] = {
                convId: conversationId,
                aiMsgId,
                content: fullContent,
                sources,
              }
              setPartial(updated)
              partialRef.current = updated
              subscribersRef.current.forEach((cb) => cb(updated))
            }
          }
        }
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : '未知'
        const errored: ChatState['partial'] = {
          ...partialRef.current!,
          content: fullContent + `\n\n[错误: ${errMsg}]`,
        }
        setPartial(errored)
        partialRef.current = errored
        subscribersRef.current.forEach((cb) => cb(errored))
      } finally {
        setIsLoading(false)
        setStreamingConvId(null)
      }
    },
    [isLoading],
  )

  return (
    <ChatContext.Provider
      value={{ isLoading, streamingConvId, partial, sendMessage, subscribe, getPartial }}
    >
      {children}
    </ChatContext.Provider>
  )
}
