# 类型安全

> InterviewRAG 前端 TypeScript 规范

---

## 核心规则

- **严格模式**：`tsconfig.json` 中 `"strict": true`
- **禁止 `any`**：用 `unknown` 代替，再用类型守卫收窄
- **API 响应必须有类型**：所有 API 返回值必须定义 TypeScript 接口

---

## 类型定义位置

```typescript
// lib/types.ts — 集中管理所有类型

export interface QueryRequest {
  question: string
  top_k?: number
}

export interface QueryResponse {
  answer: string
  sources: Source[]
}

export interface Source {
  id: string
  question: string
  answer: string
  score: number
}

export interface ApiError {
  detail: string
  status_code: number
}
```

---

## 规则

- 组件 Props 必须用 `interface` 定义
- API 调用函数必须有返回类型标注
- 枚举用 `as const` 而不是 `enum`
- 不用类型断言（`as`），除非有注释说明原因

---

## 禁止事项

- ❌ `any` 类型
- ❌ `@ts-ignore` / `@ts-nocheck`
- ❌ 类型断言无注释
