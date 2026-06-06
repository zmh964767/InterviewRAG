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
- 测试用 Jest + React Testing Library
- 测试覆盖率目标：核心组件 80%+

---

## 代码审查清单

- [ ] 组件有 TypeScript Props 接口
- [ ] 异步操作有 loading/error 处理
- [ ] 列表项有 key prop
- [ ] 没有 `any` 类型
- [ ] 样式用 Tailwind，无内联样式
- [ ] 组件不超过 150 行
