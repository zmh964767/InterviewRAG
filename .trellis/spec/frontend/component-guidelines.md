# 组件规范

> InterviewRAG 前端组件编写标准

---

## 组件结构

每个组件文件按以下顺序组织：

```tsx
// 1. 导入
import { type FC } from 'react'

// 2. Props 类型
interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

// 3. 组件
export const ChatMessage: FC<ChatMessageProps> = ({ role, content, sources }) => {
  return (
    <div className={role === 'user' ? '...' : '...'}>
      <p>{content}</p>
      {sources?.map(s => <SourceCard key={s.id} source={s} />)}
    </div>
  )
}
```

---

## Props 规范

- 必须用 `interface` 定义 Props（不用 `type`，除非是联合类型）
- Props 尽量扁平，不传嵌套对象
- 回调函数用 `on` 前缀：`onSubmit`、`onRetry`
- 可选 Props 用 `?` 标记并提供默认值

---

## 样式规范

- **只用 Tailwind CSS**，不用 CSS Modules 或 styled-components
- 响应式：用 `sm:`、`md:`、`lg:` 前缀
- 深色模式：用 `dark:` 前缀（MVP 可选）
- 不自定义 Tailwind 主题，除非有设计系统

---

## 禁止事项

- ❌ 组件内直接写 `fetch()` 调用
- ❌ 组件内写业务逻辑（应放 hooks 或 lib）
- ❌ 使用 `any` 类型
- ❌ 组件超过 150 行（拆分子组件）
- ❌ 内联样式（用 Tailwind）

---

## 常见错误

- 忘记给列表项加 `key` prop
- 在渲染函数里创建新对象（导致不必要的重渲染）
- 不处理 loading 和 error 状态
