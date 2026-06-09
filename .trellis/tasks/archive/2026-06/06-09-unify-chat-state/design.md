# 统一 chat 状态管理 — 技术设计

## 1. 架构对比

### 修复前（多实例）
```
app/layout.tsx (ChatProvider)
  ├─ ChatContext  → isLoading, streamingConvId, partial
  └─ ConversationsBootstrap (hack: useConversations() 只为触发 hook)
       └─ app/page.tsx (Home)
            ├─ useConversations()  // 独立实例 1
            │   └─ localStorage useState/useEffect
            ├─ useChatContext()     // 跨路由 state
            ├─ messagesMapRef       // 运行时缓存
            └─ displayMessages      // UI 渲染
```

### 修复后（单实例）
```
app/layout.tsx (ChatProvider)   ← 单一 useState/useEffect 入口
  ├─ ChatContext
  │   ├─ conversations: Conversation[]   // 来自 useConversations
  │   ├─ currentId: string | null
  │   ├─ partial: StreamPartial | null
  │   ├─ 流式 partial 实时同步到 conversations[convId].messages
  │   └─ CRUD: create/switch/delete/rename/updateMessages
  └─ app/page.tsx (Home)
       ├─ useChatContext()  // 唯一数据源
       └─ displayMessages = conversations.find(c => c.id === currentId)?.messages || []
```

## 2. ChatContext 接口扩展

```typescript
interface ChatContextValue {
  // 流式状态
  isLoading: boolean
  streamingConvId: string | null
  partial: StreamPartial | null

  // 流式控制
  sendMessage(content: string, convId: string): Promise<void>
  subscribe(cb: (partial: StreamPartial | null) => void): () => void

  // 对话管理（从 useConversations 迁入）
  conversations: Conversation[]
  currentId: string | null
  currentConversation: Conversation | null
  currentMessages: Message[]  // 派生：conversations.find(c => c.id === currentId)?.messages
  createConversation(): string
  switchConversation(id: string): void
  deleteConversation(id: string): void
  updateMessages(msgs: Message[]): void  // 同时持久化 + 通知
  renameConversation(id: string, title: string): void
}
```

## 3. 流式 partial 同步策略

### 3.1 关键时序

```
partial 更新 (from useChatContext.sendMessage)
  ↓
ChatProvider 收到 partial（包含 convId、aiMsgId、content、sources）
  ↓
按 partial.convId 查找 conversations（不依赖 currentId！用户可能流式中途切对话）
  ↓
合并到 conversations[partial.convId].messages：
  - 找到 aiMsgId 替换 content + sources
  - 找不到则 append 新 ai message
  ↓
debounced write to localStorage (100ms)
```

**关键不变量**：`partial` 自带 `convId`，**不依赖 `currentId`**。用户可能：
- 流式进行中切到其他对话 → `currentId` 变，但 `partial.convId` 不变
- 流式进行中刷新页面 → `partial` 丢失，但 `conversations[convId].messages` 已持久化

### 3.2 sendMessage 内部三步

之前 `page.tsx` 手动做"写 user + 写空 ai + 启流"三步。**修复后**：`sendMessage` 内部完成：

```
sendMessage(content, convId)
  → 1. 写 user message 到 conversations[convId].messages
  → 2. 写空 ai message（aiMsgId = Date.now()+1）到 conversations[convId].messages
  → 3. setPartial({convId, aiMsgId, content: '', sources: []})  // 触发订阅者
  → 4. for-await 流 → 每个 chunk 更新 partial
```

**page.tsx 的 handleSend 简化**：仅做"创建对话（如需要）→ 调 sendMessage"。

### 3.3 为什么不在 subscribe 里同步？

- subscribe 是 fire-and-forget，page.tsx 可能卸载（即使切回也会重订阅）
- ChatProvider 拥有完整 state，能**可靠**地合并 partial + 触发 setConversations
- 单一 `setConversations` 调用 = 单一 localStorage 写入点 = 无竞争

## 4. localStorage 写入策略

**单一入口**：ChatProvider 内部的 `useEffect([conversations])`，debounce 100ms。

```typescript
// ChatProvider 内部
useEffect(() => {
  if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
  saveTimerRef.current = setTimeout(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
    localStorage.setItem(ACTIVE_KEY, currentId ?? '')
  }, 100)
  return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
}, [conversations, currentId])
```

**好处**：
- 多次 setConversations 连续调用被合并
- 卸载时 cleanup 立即 flush（无丢失）
- 单点写入 = 零竞争

## 5. 关键文件变更

| 文件 | 变更 |
|---|---|
| `contexts/ChatContext.tsx` | 合并 useConversations 状态 + actions + partial 同步 |
| `hooks/useConversations.ts` | **保留导出**，改为 adapter（从 ChatContext 转发）|
| `app/layout.tsx` | 删除 ConversationsBootstrap；只渲染 ChatProvider |
| `app/page.tsx` | 删除 useConversations() + messagesMapRef；统一从 useChatContext 消费 |
| `components/layout/Sidebar.tsx` | 改用 type import（不直接调 hook） |
| `hooks/__tests__/ChatContext.test.tsx` | 新增单测（覆盖：CRUD + partial 同步 + localStorage 持久化）|

## 6. 兼容性策略

`useConversations.ts` 保留导出，**完全保持旧接口**（包括 `messages` 和 `currentMessages` 两个字段都返回 `currentMessages`）。Sidebar 仍可 `import type { Conversation }`；page.tsx 改用 `useChatContext()`，但 useConversations 仍然兼容（adapter）。

**Adapter 完整签名**：
```typescript
export function useConversations() {
  const ctx = useChatContext()
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
