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
