# 统一 chat 状态管理 — 实施计划

## 1. 实施步骤（按依赖顺序）

### Step 1：扩展 ChatContext 包含 conversations state
- 修改 `contexts/ChatContext.tsx`
- 内联 useConversations 的 state + actions
- localStorage 持久化逻辑搬过来
- 添加 `currentMessages` 派生值

### Step 2：流式 partial 同步
- 在 ChatProvider 内部，subscribe 自己（用 ref 持有 callback）
- partial 更新时，自动合并到 `conversations[convId].messages` 并触发 setConversations
- debounce 100ms 写 localStorage

### Step 3：useConversations 改 adapter
- 保留导出签名（不破坏 Sidebar 等 type import）
- 内部从 `useChatContext()` 转发所有值

### Step 4：删除 ConversationsBootstrap
- 修改 `app/layout.tsx`
- ChatProvider 单独渲染，不再嵌套 ConversationsBootstrap

### Step 5：page.tsx 改用 useChatContext
- 删除 `useConversations` 调用
- 所有 conversations 状态从 `useChatContext()` 取
- `displayMessages` 简化为 `currentMessages`（Context 已算好）

### Step 6：单测
- `hooks/__tests__/useConversations.test.ts`
- 覆盖：create / switch / delete / rename / updateMessages / 持久化
- 覆盖：partial 同步到 conversations

## 2. 验证命令

```bash
# TypeScript 检查
cd frontend && npx tsc --noEmit

# Build
cd frontend && npm run build

# 浏览器手测：
# 1. 发送问题 → 看到流式生成
# 2. 切到知识库 → 切回对话 → 内容保留
# 3. 刷新页面 → 看到上次内容
# 4. 多发几条消息 → 切换对话 → 切换回来 → 内容正确
```

## 3. 关键风险

| 风险 | 缓解 |
|---|---|
| localStorage 写入竞争 | 单一 setConversations 入口 |
| 流式 partial 同步遗漏 | ChatProvider 内部 subscribe + useEffect 双向保障 |
| Context 嵌套误用 | 单元测试 + 注释说明 |
| 现有 page.tsx 行为破坏 | adapter 模式 |

## 4. 单元测试覆盖场景

`hooks/__tests__/ChatContext.test.tsx`（新增）：

```typescript
describe('ChatContext', () => {
  // 基础 CRUD
  test('createConversation 创建新对话并设为当前')
  test('switchConversation 切换 currentId')
  test('deleteConversation 删除并切到下一个')
  test('deleteConversation 删除最后一个 → 自动创建新对话')
  test('renameConversation 修改标题')
  test('updateMessages 写入 messages + 更新 title（如果 title="新对话"）')

  // 持久化
  test('刷新页面：从 localStorage 恢复 conversations 和 currentId')
  test('每次 setConversations 触发 localStorage 写入（debounce 100ms）')

  // 流式 partial 同步（核心）
  test('partial 更新 → 实时合并到 conversations[convId].messages')
  test('partial 更新使用 partial.convId 而非 currentId（用户流式切走时）')
  test('流完成 → partial 保留为最后一个值（不重置为 null）')
  test('订阅者收到 partial 通知')

  // 兼容性
  test('useConversations adapter 仍返回正确接口（外部调用方零破坏）')
})
```

## 5. 实施顺序（细化）

1. **Step 1**：扩展 ChatContext（合并 conversations + localStorage + 流式同步）
2. **Step 2**：写单测 ChatContext.test.tsx
3. **Step 3**：改 useConversations 为 adapter
4. **Step 4**：删 layout 的 ConversationsBootstrap
5. **Step 5**：改 page.tsx 用 useChatContext
6. **Step 6**：npx tsc --noEmit + npm run build 验证
7. **Step 7**：浏览器手测（发送 → 切走 → 切回 → 刷新页面）
8. **Step 8**：commit

每个 step 都要 npx tsc --noEmit 通过。
