# 自定义 Hooks 规范

> InterviewRAG 前端 Hooks 编写标准

---

## 核心 Hook: useChat

对话管理的主要 Hook：

```tsx
// hooks/useChat.ts
export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = async (content: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.query(content)
      setMessages(prev => [...prev, /* user msg */, /* assistant msg */])
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return { messages, isLoading, error, sendMessage }
}
```

---

## 规则

- Hook 命名必须以 `use` 开头
- 每个 Hook 只负责一件事（单一职责）
- 异步操作必须处理 loading 和 error 状态
- 不在 Hook 里做 UI 渲染逻辑
- 返回值用对象 `{}`，不用数组 `[]`（便于解构）

---

## 禁止事项

- ❌ 在 Hook 里直接操作 DOM
- ❌ 在 Hook 里用 `any` 类型
- ❌ 条件调用 Hook（违反 Rules of Hooks）
