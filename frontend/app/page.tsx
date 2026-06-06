'use client'

import { ChatHistory } from '@/components/chat/ChatHistory'
import { ChatInput } from '@/components/chat/ChatInput'
import { useChat } from '@/hooks/useChat'

export default function Home() {
  const { messages, isLoading, error, sendMessage, clearMessages } = useChat()

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Header */}
      <header className="border-b bg-white px-4 py-3 shrink-0">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            <div>
              <h1 className="text-lg font-semibold text-gray-900">
                InterviewRAG
              </h1>
              <p className="text-xs text-gray-500">
                基于 RAG 的面试题库问答系统
              </p>
            </div>
          </div>
          {messages.length > 0 && (
            <button
              onClick={clearMessages}
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              清空对话
            </button>
          )}
        </div>
      </header>

      {/* Chat Area */}
      <ChatHistory messages={messages} isLoading={isLoading} />

      {/* Error Display */}
      {error && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-100">
          <p className="text-sm text-red-600 text-center">{error}</p>
        </div>
      )}

      {/* Input */}
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  )
}
