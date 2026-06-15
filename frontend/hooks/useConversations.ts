'use client'

import { useChatConversationsContext } from '@/contexts/ChatContext'

// =====================================================================
// useConversations: 薄 adapter（向后兼容）
// 所有 state 实际由 ChatProvider 持有，本 hook 仅做字段转发。
// 改用 useChatConversationsContext 以避免订阅流式状态。
// =====================================================================

export type { Conversation } from '@/contexts/ChatContext'

export function useConversations() {
  const ctx = useChatConversationsContext()
  return {
    conversations: ctx.conversations,
    currentId: ctx.currentId,
    currentConversation: ctx.currentConversation,
    // 旧接口叫 messages，新接口叫 currentMessages，两个都给
    messages: ctx.currentMessages,
    currentMessages: ctx.currentMessages,
    createConversation: ctx.createConversation,
    switchConversation: ctx.switchConversation,
    deleteConversation: ctx.deleteConversation,
    updateMessages: ctx.updateMessages,
    renameConversation: ctx.renameConversation,
  }
}
