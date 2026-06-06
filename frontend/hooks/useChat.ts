'use client'

import { useState, useCallback, useRef } from 'react'
import { queryStream } from '@/lib/api'
import type { Message, SourceRef } from '@/lib/types'

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const conversationIdRef = useRef<string | undefined>(undefined)

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return

    setError(null)
    setIsLoading(true)

    // 添加用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMessage])

    // 添加 AI 消息占位
    const aiMessageId = (Date.now() + 1).toString()
    const aiMessage: Message = {
      id: aiMessageId,
      role: 'assistant',
      content: '',
      sources: [],
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, aiMessage])

    try {
      let fullContent = ''
      let sources: SourceRef[] = []

      for await (const event of queryStream(content, conversationIdRef.current)) {
        if (event.error) {
          throw new Error(event.error)
        }

        if (event.content) {
          fullContent += event.content
          // 实时更新 AI 消息
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMessageId ? { ...m, content: fullContent } : m,
            ),
          )
        }

        if (event.done && event.conversation_id) {
          conversationIdRef.current = event.conversation_id
          if (event.sources) {
            sources = event.sources
          }
        }
      }

      // 最终更新（包含来源）
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMessageId
            ? { ...m, content: fullContent, sources }
            : m,
        ),
      )
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '请求失败'
      setError(errorMsg)
      // 更新 AI 消息为错误提示
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMessageId
            ? { ...m, content: `抱歉，出现了错误：${errorMsg}` }
            : m,
        ),
      )
    } finally {
      setIsLoading(false)
    }
  }, [isLoading])

  const clearMessages = useCallback(() => {
    setMessages([])
    setError(null)
    conversationIdRef.current = undefined
  }, [])

  // 加载历史消息（切换对话时使用）
  const loadMessages = useCallback((history: Message[]) => {
    setMessages(history)
    setError(null)
    conversationIdRef.current = undefined
  }, [])

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    loadMessages,
  }
}
