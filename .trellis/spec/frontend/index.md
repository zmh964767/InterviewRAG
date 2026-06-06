# 前端开发规范

> InterviewRAG 前端开发最佳实践（Next.js + Tailwind CSS）

---

## 技术栈

- **框架**：Next.js (App Router)
- **样式**：Tailwind CSS
- **语言**：TypeScript（严格模式）
- **状态管理**：组件级 Hook（无全局状态库）

---

## 规范索引

| 规范 | 描述 | 状态 |
|------|------|------|
| [目录结构](./directory-structure.md) | 模块组织和文件布局 | ✅ 已完成 |
| [组件规范](./component-guidelines.md) | 组件模式、Props、组合 | ✅ 已完成 |
| [Hook 规范](./hook-guidelines.md) | 自定义 Hooks、数据获取 | ✅ 已完成 |
| [状态管理](./state-management.md) | 本地状态、服务端状态 | ✅ 已完成 |
| [质量规范](./quality-guidelines.md) | 代码标准、禁止模式 | ✅ 已完成 |
| [类型安全](./type-safety.md) | 类型模式、校验 | ✅ 已完成 |

---

## 开发前检查清单

- [ ] 确认 Node.js 版本 >= 18
- [ ] 确认已安装依赖：`npm install`
- [ ] 确认环境变量已配置（后端 API 地址）
- [ ] 确认 TypeScript 严格模式已开启

---

## 质量检查

- [ ] 所有组件有 TypeScript Props 接口
- [ ] 无 `any` 类型
- [ ] 无内联样式
- [ ] loading/error 状态已处理
- [ ] 核心组件有测试
