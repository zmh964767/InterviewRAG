# 统一 chat 状态管理

## Goal

把 chat 模块的状态合并到单一 context，消除多实例的 localStorage 同步隐患，确保路由切换 / 刷新页面 / 切回对话时流式内容和对话列表始终一致。

## Confirmed Facts（来自代码）

### 当前状态分散
- `useConversations()` 在 **2 个地方实例化**：
  - `app/layout.tsx:32` 的 `ConversationsBootstrap` 组件（只调用，不用返回值）
  - `app/page.tsx:24`（消费返回值用于 `conversations`/`currentId`/CRUD）
- 两者都通过 `useEffect` 监听 localStorage 变化 → setState，**实际能跨实例同步**（每次都从 localStorage 读），但有 **闪烁和竞争条件**

### 三层状态
1. **`useConversations`** → `conversations[]` + `currentId`（持久化到 localStorage）
2. **`ChatContext`** → 流式 `partial`（存活于 layout，跨路由保留）
3. **`page.tsx` 内部** → `messagesMapRef`（运行时缓存，不持久化，从 localStorage conversations 恢复）

### 数据流（修复前）
```
sendMessage(content)
  → useChatContext.sendMessage()  // ChatContext 持有
    → for-await chunk
      → subscribers.forEach(cb => cb(partial))  // 通知 page.tsx
        → page.tsx subscribe 回调
          → 写入 messagesMapRef
            → 但 messagesMapRef 不写入 useConversations!
              → 用户刷新页面 → 从 localStorage 读到的是切走前的旧内容（如果 100ms debounce 还没触发）
```

### 关键问题
- 流式 partial 在 ChatContext 里是**孤立 state**，不与 `useConversations` 的 conversations 同步
- `ConversationsBootstrap` 调 `useConversations()` 不消费返回值 — 纯 hook 副作用调用（hack）
- 多次 `useConversations` 实例化浪费 React state slot

## Scope

### In Scope（MVP 范围）
- ✅ 把 `useConversations` 的 state + actions **合并进 ChatContext**
- ✅ 让 `partial` 流式变更**实时同步**到 `conversations[convId].messages`
- ✅ 删除 `ConversationsBootstrap`（不再需要 hack 调用）
- ✅ `page.tsx` 不再调 `useConversations`，从 `useChatContext()` 消费
- ✅ 单一 `localStorage` 写入点（避免竞争）
- ✅ 写单测覆盖：创建/切换/删除/更新消息 → localStorage 持久化

### Out of Scope（不做）
- ❌ 持久化到后端（保持 localStorage）
- ❌ 多 tab 同步（用 BroadcastChannel 等）— 不是当前痛点
- ❌ 撤销/重做（流式不可逆）
- ❌ 导出对话 — 单独功能

## Acceptance Criteria

- [ ] `useChatContext()` 暴露 `conversations`、`currentId`、`currentMessages`、CRUD actions
- [ ] 发送消息 → partial 实时写入 `conversations[currentId].messages` → 100ms 内 flush 到 localStorage
- [ ] 路由切到 `/kb` 再切回 `/`，流持续生成，切回时 `displayMessages` 显示最新内容
- [ ] 刷新页面后能从 localStorage 恢复完整消息（包括上次未完成的流——如有 partial 残留）
- [ ] 单一 `useConversations` 调用（来自 ChatProvider），不再有 ConversationsBootstrap hack
- [ ] 单元测试：所有 conversations CRUD + 流式 partial 同步
- [ ] 现有 `useConversations` 接口**完全保留**（外部调用方零改动）

## Notes

- 复杂度：**Complex**（涉及 React Context 重构、跨实例同步、localStorage 竞争）
- 关键风险：多个 `useConversations` 实例 → 多个 React state → race condition
- 兼容性：`useConversations` 保留导出（adapter 模式），外部调用方零改动
- **Review 发现 4 处需要细化**（已修正到 design.md/implement.md）：
  1. 流式 partial 同步策略需明确"按 convId 而非 currentId"（用户可能流式中途切到其他对话）
  2. `sendMessage` 需要内部完成"写 user message + 写空 ai message + 启动流"三步（之前由 page.tsx 分散做）
  3. localStorage debounce 策略 + 单一写入点要写明
  4. 单元测试要列具体覆盖场景
