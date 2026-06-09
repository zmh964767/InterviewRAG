'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { queryStream } from '@/lib/api'
import type { Message, SourceRef } from '@/lib/types'

interface UseChatOptions {
  onMessageUpdate: (conversationId: string, messages: Message[]) => void
  getMessages: (conversationId: string) => Message[]
}

export function useChat({ onMessageUpdate, getMessages }: UseChatOptions) {
  const [isLoading, setIsLoading] = useState(false)
  const streamingConvIdRef = useRef<string | null>(null)
  // 用 ref 保存流式 partial content，组件 unmount/路由切换也不丢
  const partialRef = useRef<{ convId: string; aiMsgId: string; content: string; sources: SourceRef[] } | null>(null)

  // 组件 unmount 时把 partial content 写回 store
  useEffect(() => {
    return () => {
      const p = partialRef.current
      if (p && p.content) {
        const msgs = getMessages(p.convId)
        onMessageUpdate(
          p.convId,
          msgs.map((m) =>
            m.id === p.aiMsgId ? { ...m, content: p.content + '…' } : m,
          ),
        )
        partialRef.current = null
      }
    }
  }, [onMessageUpdate, getMessages])

  const sendMessage = useCallback(async (content: string, conversationId: string) => {
    if (!content.trim() || isLoading) return

    setIsLoading(true)
    streamingConvIdRef.current = conversationId

    const currentMessages = getMessages(conversationId)

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }

    const aiMessageId = (Date.now() + 1).toString()
    const aiMessage: Message = {
      id: aiMessageId,
      role: 'assistant',
      content: '',
      sources: [],
      timestamp: Date.now(),
    }

    onMessageUpdate(conversationId, [...currentMessages, userMessage, aiMessage])

    // 初始化 partial 状态
    partialRef.current = { convId: conversationId, aiMsgId: aiMessageId, content: '', sources: [] }

    try {
      // 构建对话历史（排除最后的 AI 占位消息）
      const historyForApi = currentMessages
        .filter((m) => m.content)
        .map((m) => ({ role: m.role, content: m.content }))

      let fullContent = ''
      let sources: SourceRef[] = []
      let backendConvId: string | undefined = undefined

      try {
        for await (const event of queryStream(content, backendConvId, historyForApi)) {
          if (event.error) throw new Error(event.error)

          if (event.content) {
            fullContent += event.content
            if (partialRef.current) {
              partialRef.current.content = fullContent
            }
            const latest = getMessages(conversationId)
            onMessageUpdate(
              conversationId,
              latest.map((m) =>
                m.id === aiMessageId ? { ...m, content: fullContent } : m,
              ),
            )
          }

          if (event.done) {
            if (event.conversation_id) backendConvId = event.conversation_id
            if (event.sources) {
              sources = event.sources
              if (partialRef.current) {
                partialRef.current.sources = sources
              }
            }
          }
        }
      } catch (innerErr) {
        // 流被中断（CancelledError 或网络错误），partial 已被 ref 保存
        throw innerErr
      }

      const final = getMessages(conversationId)
      onMessageUpdate(
        conversationId,
        final.map((m) =>
          m.id === aiMessageId ? { ...m, content: fullContent, sources } : m,
        ),
      )
      partialRef.current = null
    } catch (err) {
      // 流被中断时 err 是空或 CancelledError，partial 已被 useEffect cleanup 写回
      const latest = getMessages(conversationId)
      const partial = partialRef.current?.content || ''
      if (partial) {
        // 已经有部分内容被 useEffect cleanup 写过，这里不再覆盖
        partialRef.current = null
      } else {
        onMessageUpdate(
          conversationId,
          latest.map((m) =>
            m.id === aiMessageId ? { ...m, content: `抱歉，出现了错误：${err instanceof Error ? err.message : '请求失败'}` } : m,
          ),
        )
      }
    } finally {
      setIsLoading(false)
      streamingConvIdRef.current = null
    }
  }, [isLoading, onMessageUpdate, getMessages])

  return {
    sendMessage,
    isLoading,
    streamingConvId: streamingConvIdRef,
  }
}
