# 前端质量规范

> InterviewRAG 前端代码质量标准

---

## 必须遵守的模式

- 所有组件必须有 TypeScript Props 接口定义
- 所有 API 调用必须通过 `lib/api.ts` 封装
- 所有异步操作必须处理 loading 和 error 状态
- 所有列表渲染必须有 `key` prop

---

## 禁止模式

- ❌ 使用 `any` 类型
- ❌ 组件内直接写 `fetch()` 调用
- ❌ 内联样式（用 Tailwind CSS）
- ❌ 组件超过 150 行（拆分子组件）
- ❌ `@ts-ignore` / `@ts-nocheck`
- ❌ 在渲染函数里创建新对象（导致不必要的重渲染）

---

## 测试要求

- 核心组件（`ChatMessage`、`ChatInput`）必须有单元测试
- API 调用函数必须有 mock 测试
- 测试用 Jest + React Testing Library(改用 Vitest,见下方迁移说明)
- 测试覆盖率目标：核心组件 80%+

### 测试框架:Vitest(2026-06 迁移)

项目从默认 Jest 迁移到 **Vitest**(2026-06 unify-chat-state 任务引入):
- 零配置,内置 TS + jsdom
- 安装: `npm install -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom jsdom`
- 配置: `frontend/vitest.config.ts`(jsdom env, `@/` path alias, oxc JSX automatic runtime)
- scripts: `"test": "vitest run"`, `"test:watch": "vitest"`
- setup: `frontend/vitest.setup.ts` 注册 `@testing-library/jest-dom/vitest`
- 测试文件位置: `hooks/__tests__/<name>.test.tsx` 或 `__tests__/` 目录

**vitest 4 注意事项**:
- 4.x 默认用 oxc transformer,**忽略 esbuild 配置**;JSX 需要 `"jsxImportSource": "react"` 或在 tsconfig 配 automatic runtime
- `vi.mock('@/lib/api')` 在文件顶部声明,返回 `async function*` 模拟 SSE 流

### Context / Provider 测试模式

测 Context 时,**避免直接 renderHook** 的复杂性(React 18 strict mode 下的双 mount + act 包裹麻烦)。推荐模式:写一个 `<TestHarness>` 组件,内部调 hook,通过 DOM 暴露状态:

```tsx
function TestHarness() {
  const ctx = useChatContext()
  return <div data-testid="state" data-conv-count={ctx.conversations.length} />
}

function renderWithProvider() {
  return render(<ChatProvider><TestHarness /></ChatProvider>)
}
```

但对于纯数据 / 不需要 React 树的场景,`renderHook` + `act` 仍然合适。

---

## 代码审查清单

- [ ] 组件有 TypeScript Props 接口
- [ ] 异步操作有 loading/error 处理
- [ ] 列表项有 key prop
- [ ] 没有 `any` 类型
- [ ] 样式用 Tailwind，无内联样式
- [ ] 组件不超过 150 行
