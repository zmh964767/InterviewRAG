# 前端目录结构

> InterviewRAG 前端代码组织方式（Next.js App Router）

---

## 目录布局

```
frontend/
├── app/                    # Next.js App Router 页面
│   ├── layout.tsx          # 全局布局（字体、主题）
│   ├── page.tsx            # 首页 / 对话入口
│   └── globals.css         # 全局样式
├── components/             # 可复用组件
│   ├── chat/               # 对话相关组件
│   │   ├── ChatInput.tsx   # 输入框
│   │   ├── ChatMessage.tsx # 单条消息
│   │   └── ChatHistory.tsx # 消息列表
│   ├── sources/            # 来源引用组件
│   │   └── SourceCard.tsx  # 单个来源卡片
│   └── ui/                 # 通用 UI 组件
│       ├── Button.tsx
│       ├── Loading.tsx
│       └── ErrorDisplay.tsx
├── lib/                    # 工具函数和 API 客户端
│   ├── api.ts              # 后端 API 调用封装
│   └── types.ts            # TypeScript 类型定义
├── hooks/                  # 自定义 Hooks
│   └── useChat.ts          # 对话状态管理
├── public/                 # 静态资源
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## 命名规范

- **组件文件**：PascalCase（`ChatMessage.tsx`）
- **工具文件**：camelCase（`api.ts`、`types.ts`）
- **目录**：kebab-case 或功能名（`chat/`、`sources/`）
- **CSS 类名**：Tailwind 原子类，不用自定义类名

---

## 规则

- 页面组件（`app/`）只做布局和数据获取，不放业务逻辑
- 业务逻辑放 `hooks/` 或 `lib/`
- 组件必须有 TypeScript props 类型定义
- 不允许在组件里直接调用 fetch，统一用 `lib/api.ts`
