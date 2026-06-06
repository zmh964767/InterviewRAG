'use client'

import { useState, useCallback, useEffect } from 'react'
import type { Message } from '@/lib/types'

const STORAGE_KEY = 'interviewrag_conversations'
const MAX_TITLE_LENGTH = 15

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: number
  updatedAt: number
}

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

function saveConversations(conversations: Conversation[]): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
  } catch {
    // localStorage full or unavailable
  }
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)

  // Load from localStorage on mount
  useEffect(() => {
    const loaded = loadConversations()
    setConversations(loaded)
    if (loaded.length > 0) {
      setCurrentId(loaded[0].id)
    }
  }, [])

  // Save to localStorage when conversations change
  useEffect(() => {
    if (conversations.length > 0) {
      saveConversations(conversations)
    }
  }, [conversations])

  const currentConversation = conversations.find((c) => c.id === currentId) || null
  const messages = currentConversation?.messages || []

  const createConversation = useCallback(() => {
    const newConv: Conversation = {
      id: generateId(),
      title: '新对话',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    setConversations((prev) => [newConv, ...prev])
    setCurrentId(newConv.id)
    return newConv.id
  }, [])

  const switchConversation = useCallback((id: string) => {
    setCurrentId(id)
  }, [])

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id)
      if (next.length === 0) {
        const newConv: Conversation = {
          id: generateId(),
          title: '新对话',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        }
        setCurrentId(newConv.id)
        return [newConv]
      }
      if (currentId === id) {
        setCurrentId(next[0].id)
      }
      return next
    })
  }, [currentId])

  const updateMessages = useCallback((msgs: Message[]) => {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== currentId) return c
        return {
          ...c,
          messages: msgs,
          title: c.title === '新对话' ? getTitleFromMessages(msgs) : c.title,
          updatedAt: Date.now(),
        }
      })
    )
  }, [currentId])

  const renameConversation = useCallback((id: string, title: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title } : c))
    )
  }, [])

  return {
    conversations,
    currentId,
    currentConversation,
    messages,
    createConversation,
    switchConversation,
    deleteConversation,
    updateMessages,
    renameConversation,
  }
}
