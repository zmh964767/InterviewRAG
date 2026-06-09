# 状态管理

> InterviewRAG 前端状态管理策略

---

## 策略

**MVP 不用全局状态管理库**（不用 Redux、Zustand 等）。

- **对话状态**：用 `useChat` Hook 管理（组件级状态）
- **服务端状态**：直接在组件中调用 API（不用 React Query，MVP 够用）
- **全局状态**：无（MVP 不需要主题切换、用户设置等）

---

## 数据流

```
用户输入 → useChat.sendMessage() → API 调用 → 更新 messages 状态 → UI 渲染
```

---

## 规则

- 状态尽量靠近使用它的组件
- 避免 prop drilling 超过 2 层（如果需要，用 Context）
- 不在 localStorage 存大对象
- 错误状态必须在 UI 中展示给用户

---

## Context 持久化的反模式 → 修正模式

### 反模式：跨组件重复 useState + useEffect 同步 localStorage

```tsx
// ❌ 错：同一个 hook 在 layout 和 page 各调一次
// app/layout.tsx
function ConversationsBootstrap() {
  useConversations()  // 只为触发 hook，不消费返回值 (hack)
  return children
}

// app/page.tsx
const { conversations, createConversation } = useConversations()  // 独立 React state
```

后果：两份 React state、两份 `useEffect` 监听 localStorage → 竞争、闪烁、流式 partial 落空。

### 修正模式：单实例 Provider + 单一 localStorage 写入点

```tsx
// ✅ app/layout.tsx
<ChatProvider>  // 内部唯一调 useState + useEffect 同步 localStorage
  {children}
</ChatProvider>

// app/page.tsx
const { conversations, createConversation } = useChatContext()  // 消费唯一数据源
```

**单一 ChatProvider 内部规则**:
- 一次 `useState` 管 `conversations` + `currentId`
- 一次 `useEffect` 加载 localStorage(挂载时)
- 一次 `useEffect` 持久化(用 `clearTimeout` + `setTimeout(..., 100)` debounce)
- **必须有 hydration guard**:`hasHydratedRef` 标记首次加载完成,避免初始空 `[]` 覆盖已持久化数据

```tsx
const hasHydratedRef = useRef(false)

useEffect(() => {
  // 加载 localStorage
  const loaded = loadConversations()
  setConversations(loaded)
  hasHydratedRef.current = true
}, [])

useEffect(() => {
  if (!hasHydratedRef.current) return  // 关键:首次空 state 不写入
  const t = setTimeout(() => {
    localStorage.setItem(KEY, JSON.stringify(conversations))
  }, 100)
  return () => clearTimeout(t)
}, [conversations])
```

**为什么必须 hydration guard**:
- React 18 严格模式 + Strict Mode 双 mount 会让 effect 跑两次
- 第一次 render 拿到 `conversations = []` 就触发写入 → 已有数据被清空
- guard 保证只在 load 完成后才允许写回

### 兼容性:Adapter 模式保留旧 hook

如果别的组件(比如 Sidebar)仍在用旧 hook,把它改造成 thin adapter 从 Context 转发,**保留所有旧字段**(包括 `messages` 和 `currentMessages` 这种 alias 重复字段):

```tsx
// hooks/useConversations.ts
export function useConversations() {
  const ctx = useChatContext()
  return {
    conversations: ctx.conversations,
    currentId: ctx.currentId,
    currentConversation: ctx.currentConversation,
    messages: ctx.currentMessages,        // 旧字段
    currentMessages: ctx.currentMessages, // 新字段
    createConversation: ctx.createConversation,
    // ...
  }
}
```

零破坏外部调用方;`Conversation` interface 也继续 export 给 `import type` 用。

### 流式 partial 合并:按 `partial.convId` 不按 `currentId`

流式 SSE 在 ChatProvider 内部合并到 conversations,关键是 **partial 自带 convId**,不依赖当前 `currentId`:

```tsx
// ✅ ChatProvider 内部
function mergePartial(partial: StreamPartial, prev: Conversation[]): Conversation[] {
  return prev.map(conv => {
    if (conv.id !== partial.convId) return conv  // 关键:用 partial.convId 不是 currentId
    return {
      ...conv,
      messages: conv.messages.map(m =>
        m.id === partial.aiMsgId
          ? { ...m, content: partial.content, sources: partial.sources }
          : m
      ),
    }
  })
}
```

原因:用户可能流式中途切到其他对话,`currentId` 会变,但 partial 仍属于原对话。
