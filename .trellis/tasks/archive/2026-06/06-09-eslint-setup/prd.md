# ESLint 接入

## Goal

给项目加 ESLint，让所有后续改动有 lint 门守护，不再依赖作者记忆不写 `any` / 不用内联样式。

## Confirmed Facts

- 项目原本没有 ESLint 配置（`npx next lint` 触发交互式 prompt，没有 `.eslintrc.json`）
- Next.js 14 官方推荐 `@next/eslint-plugin-next`，安装 `eslint-config-next` 即可
- TypeScript 项目应加 `@typescript-eslint/eslint-plugin`
- `npm run lint` 已在 `package.json` 里定义（`"lint": "next lint"`），但无配置文件所以会卡住

## Scope

### In Scope
- [ ] 安装 `eslint` + `eslint-config-next` + `@typescript-eslint/parser`（通过 `npx next lint --eslint-config ...` 或直接安装）
- [ ] 创建 `.eslintrc.json`（Next.js + TypeScript 推荐规则）
- [ ] 运行 `npm run lint -- --fix` 修复所有 auto-fixable 问题
- [ ] 手动修复剩余的 lint 问题（如 `any`、未使用变量等）
- [ ] `npm run build` 通过
- [ ] `npm test` 20/20 通过

### Out of Scope
- Prettier（代码格式化）—— 另一个任务
- CI/CD 集成 —— 部署配置另行讨论
- 自定义规则（只用 Next.js 官方推荐规则集）

## Acceptance Criteria

- [ ] `.eslintrc.json` 存在，extends 包含 `next/core-web-vitals` 和 `next/typescript`
- [ ] `npm run lint` 无 error（warning 可接受）
- [ ] `npm run build` 通过
- [ ] 现有代码的 `any` 类型被 lint 规则捕获（如 `@typescript-eslint/no-explicit-any`）
- [ ] Git diff 里不含 .next/ 或 node_modules/ 变动

## Notes

- Light task：PRD-only，不需要 design.md / implement.md
- 依赖 `eslint-config-next`（Next.js 官方包），已随 Next.js 14 内置
