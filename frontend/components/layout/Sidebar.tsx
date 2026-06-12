'use client'

import { usePathname, useRouter } from 'next/navigation'
import type { Conversation } from '@/hooks/useConversations'
import { A11Y } from '@/lib/copy'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  stats?: unknown  // 保留传参能力但当前不再使用
  conversations: Conversation[]
  currentId: string | null
  onCreateConversation: () => void
  onSwitchConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
}

type Tab = 'conversations' | 'questions'

export function Sidebar({
  isOpen, onToggle,
  conversations, currentId,
  onCreateConversation, onSwitchConversation, onDeleteConversation,
}: SidebarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const activeTab: Tab = pathname?.startsWith('/questions') ? 'questions' : 'conversations'

  const handleTabClick = (tab: Tab) => {
    if (tab === 'conversations') {
      router.push('/')
    } else if (tab === 'questions') {
      router.push('/questions')
    }
  }

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 lg:hidden"
          style={{ background: 'rgba(26, 22, 18, 0.3)', backdropFilter: 'blur(2px)' }}
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static z-40 h-full w-72 flex flex-col transition-transform duration-300 ease-in-out border-r ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0 lg:w-0 lg:overflow-hidden'
        }`}
        style={{ background: 'var(--paper)', borderColor: 'var(--border)' }}
      >
        {/* Header */}
        <div className="h-14 px-5 flex items-center justify-between shrink-0 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--ink)' }}>
              <span className="text-sm" style={{ fontFamily: 'var(--font-display)', color: 'var(--cream)', fontWeight: 600 }}>R</span>
            </div>
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--ink)', letterSpacing: '-0.01em' }}>
              InterviewRAG
            </span>
          </div>
          <button
            onClick={onToggle}
            className="p-1.5 rounded-lg transition-colors lg:hidden"
            style={{ color: 'var(--ink-muted)' }}
            aria-label={A11Y.MENU}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* New Chat — 仅对话 tab */}
        {activeTab === 'conversations' && (
          <div className="p-4">
            <button
              onClick={onCreateConversation}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl transition-all"
              style={{ background: 'var(--ink)', color: 'var(--cream)' }}
              aria-label={A11Y.NEW_CHAT}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.85' }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              新建对话
            </button>
          </div>
        )}

        {/* Tabs */}
        <div className="px-4 flex gap-1 mb-2">
          {(['conversations', 'questions'] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => handleTabClick(tab)}
              className="flex-1 py-2 text-xs font-medium rounded-lg transition-all"
              style={{
                background: activeTab === tab ? 'var(--cream)' : 'transparent',
                color: activeTab === tab ? 'var(--ink)' : 'var(--ink-muted)',
                border: activeTab === tab ? '1px solid var(--border-subtle)' : '1px solid transparent',
              }}
              aria-label={tab === 'conversations' ? A11Y.SWITCH_TO_CONVERSATIONS : A11Y.SWITCH_TO_QUESTIONS}
              aria-current={activeTab === tab ? 'page' : undefined}
            >
              {tab === 'conversations' ? '对话' : '题目库'}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'conversations' ? (
          /* Conversation List */
          <div className="flex-1 overflow-y-auto px-3">
            {conversations.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-xs" style={{ color: 'var(--ink-muted)' }}>还没有对话</p>
              </div>
            ) : (
              <div className="space-y-0.5">
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className="group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all"
                    style={{
                      background: conv.id === currentId ? 'var(--cream)' : 'transparent',
                      border: conv.id === currentId ? '1px solid var(--border-subtle)' : '1px solid transparent',
                    }}
                    onClick={() => onSwitchConversation(conv.id)}
                    onMouseEnter={(e) => {
                      if (conv.id !== currentId) e.currentTarget.style.background = 'var(--cream)'
                    }}
                    onMouseLeave={(e) => {
                      if (conv.id !== currentId) e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    <svg className="w-4 h-4 shrink-0" style={{ color: 'var(--ink-muted)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                    </svg>
                    <span className="text-sm truncate flex-1" style={{ color: 'var(--ink-light)' }}>
                      {conv.title}
                    </span>
                    <button
                      className="opacity-50 group-hover:opacity-100 focus-visible:opacity-100 p-1 rounded transition-all shrink-0"
                      style={{ color: 'var(--ink-muted)' }}
                      aria-label={A11Y.DELETE_CONVERSATION}
                      onClick={(e) => {
                        e.stopPropagation()
                        onDeleteConversation(conv.id)
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ink-muted)' }}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Questions Tab — 在 /questions 页面展示，侧边栏仅提示 */
          <div className="flex-1 overflow-y-auto px-4">
            <div className="text-center py-8">
              <p className="text-xs" style={{ color: 'var(--ink-muted)' }}>题目列表在右侧页面展示</p>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 px-2 py-1.5">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--success)' }} />
            <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>GLM-4-Flash 已就绪</span>
          </div>
        </div>
      </aside>
    </>
  )
}
