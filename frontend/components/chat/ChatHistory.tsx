'use client'

import { useEffect, useRef } from 'react'
import type { Message } from '@/lib/types'
import { ChatMessage } from './ChatMessage'

interface ChatHistoryProps {
  messages: Message[]
  isLoading: boolean
}

export function ChatHistory({ messages, isLoading }: ChatHistoryProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">🤖</div>
          <h2 className="text-xl font-semibold text-gray-700 mb-2">
            InterviewRAG 面试助手
          </h2>
          <p className="text-gray-500 text-sm max-w-md">
            基于 RAG 的面试题库问答系统。输入你的面试问题，
            我会从知识库中检索相关内容并给出专业回答。
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {[
              'Transformer 自注意力机制',
              'RAG 的基本流程',
              'RLHF 训练流程',
              'MoE 是如何工作的',
            ].map((q) => (
              <span
                key={q}
                className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-full text-xs
                           hover:bg-gray-200 cursor-pointer transition-colors"
              >
                {q}
              </span>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto space-y-4">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {isLoading && messages[messages.length - 1]?.content === '' && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.1s]" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                </div>
                正在检索知识库...
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
