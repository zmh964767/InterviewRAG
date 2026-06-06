'use client'

import { useState, useCallback, useRef } from 'react'
import { queryStream } from '@/lib/api'
import type { Message, SourceRef } from '@/lib/types'

interface UseChatOptions {
  onMessageUpdate: (conversationId: string, messages: Message[]) => void
  getMessages: (conversationId: string) => Message[]
}

export function useChat({ onMessageUpdate, getMessages }: UseChatOptions) {
  const [isLoading, setIsLoading] = useState(false)
  const streamingConvIdRef = useRef<string | null>(null)

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

    try {
      // 构建对话历史（排除最后的 AI 占位消息）
      const historyForApi = currentMessages
        .filter((m) => m.content)
        .map((m) => ({ role: m.role, content: m.content }))

      let fullContent = ''
      let sources: SourceRef[] = []
      let backendConvId: string | undefined = undefined

      for await (const event of queryStream(content, backendConvId, historyForApi)) {
        if (event.error) throw new Error(event.error)

        if (event.content) {
          fullContent += event.content
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
          if (event.sources) sources = event.sources
        }
      }

      const final = getMessages(conversationId)
      onMessageUpdate(
        conversationId,
        final.map((m) =>
          m.id === aiMessageId ? { ...m, content: fullContent, sources } : m,
        ),
      )
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '请求失败'
      const latest = getMessages(conversationId)
      onMessageUpdate(
        conversationId,
        latest.map((m) =>
          m.id === aiMessageId ? { ...m, content: `抱歉，出现了错误：${errorMsg}` } : m,
        ),
      )
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
