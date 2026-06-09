# 流式 markdown 渲染优化 + 代码高亮

## Goal

让 assistant 消息的代码块有**语法高亮**，同时保持流式 SSE 渲染不变。当前 `rehype-highlight` 已装但未接入，`highlight.js` 未装。

## Confirmed Facts(来自代码)

### 当前渲染链
```
ReactMarkdown
  remarkPlugins: [remarkGfm]     ← 表格/checkbox/autolink 已有
  rehypePlugins: []               ← 空！rehype-highlight 没接上
  components: {}                  ← 无自定义 code 渲染
```

### 依赖现状
```json
// package.json 已有
"react-markdown": "^10.1.0",
"rehype-highlight": "^7.0.2",
"remark-gfm": "^4.0.1",
"highlight.js": ???               // 未安装，rehype-highlight 依赖它
```

### CSS 现状(app/globals.css)
```css
.markdown-content pre {
  background: var(--ink);        /* 暗底 */
  color: #E8E0D8;
  border-radius: 8px;
  overflow-x: auto;
  padding: 1.25em 1.5em;
}
.markdown-content pre code {
  background: none;
  padding: 0;
  color: inherit;                 /* ← 被 highlight.js 覆盖 */
  font-size: 0.85em;
}
```
已有暗色代码块样式，但无 `.hljs-*` token 颜色。

### 流式现状
- `ChatProvider.sendMessage` → `partial.content` 每个 chunk 更新 → `ChatMessage` 重新渲染整个 `<ReactMarkdown>`
- 流式中代码块截断（` ```\nprint(` 还没收到 ` ``` ` ）不会崩溃，ReactMarkdown 会把它渲染成 inline text

### 问题链（只改 3 处）
1. `highlight.js` 没装 → `rehype-highlight` import 会成功但无高亮（降级为纯 code）
2. `ChatMessage.tsx` 没加 `rehypePlugins={[rehypeHighlight]}` prop
3. 无 highlight.js CSS 主题 → token 有 class 但无颜色

---

## Scope

### In Scope
- [ ] `npm install highlight.js`（后端依赖，让 `rehype-highlight` 生效）
- [ ] `ChatMessage.tsx` import `rehypeHighlight`，加 `rehypePlugins={[rehypeHighlight]}`
- [ ] `globals.css` 或 ChatMessage.tsx import `highlight.js/styles/github-dark.css`
- [ ] 验证：`npm run build` 通过，浏览器里 assistant 回复的代码块有 Python/JS 等语法颜色
- [ ] `npm test` 现有 20 个测试不破

### Out of Scope
- ❌ 流式截断的特殊处理（react-markdown 容错够用）
- ❌ 自定义 code block copy 按钮（已有 assistant message 级别复制）
- ❌ 暗/亮主题切换（单深色主题 github-dark 足够）
- ❌ remark-math / remark-mermaid 图表渲染（另行任务）

---

## Acceptance Criteria

- [ ] `highlight.js` 在 `package.json` dependencies 里
- [ ] `ChatMessage.tsx` 的 `<ReactMarkdown>` 有 `rehypePlugins={[rehypeHighlight]}` prop
- [ ] `github-dark` CSS 主题被引入（import 或 @import）
- [ ] 浏览器发送 "请用 Python 写一个快速排序" → assistant 回复的代码块内有 `.hljs-keyword`、`.hljs-string` 等颜色
- [ ] 流式 SSE 输出中代码块不会导致 React 渲染错误（console 无 warnings/errors）
- [ ] `npm run build` 成功
- [ ] `npm test` 20/20 still pass
- [ ] 现有 `/` `/kb` 页面样式不受影响（github-dark CSS 只作用在 .hljs class 上）

## Notes

- Active task: `.trellis/tasks/06-09-markdown-streaming` (parent: `06-09-eval-and-render`)
- 这是子任务 B;子任务 A 是"评估报告 Web 页"
- 改动面极小：**只改 3 处**（1 包安装 + 1 tsx import/prop + 1 CSS import）
- 不需要 design.md / implement.md — 可以 inline 实现
