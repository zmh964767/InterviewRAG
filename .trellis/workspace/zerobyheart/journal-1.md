# Journal - zerobyheart (Part 1)

> AI development session journal
> Started: 2026-06-06

---



## Session 1: InterviewRAG 前端体验优化 + 对话功能修复

**Date**: 2026-06-06
**Task**: InterviewRAG 前端体验优化 + 对话功能修复
**Branch**: `master`

### Summary

完成 InterviewRAG 前端全面优化：Editorial Technical 视觉设计、多会话管理（localStorage 持久化+切换+删除确认）、Markdown 渲染、流式输出修复（CORS 直连+真正逐token流式）、多轮对话上下文传递、事件循环阻塞修复（run_in_executor）、Re-ranker 国内镜像、体验细节（输入框可提前编辑、发送后清空、滚动优化）

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `8d1cb79` | (see git log) |
| `28ac338` | (see git log) |
| `69fd330` | (see git log) |
| `0e65de1` | (see git log) |
| `916f30b` | (see git log) |
| `d468924` | (see git log) |
| `08e8f40` | (see git log) |
| `1c4c3e1` | (see git log) |
| `b31b6e9` | (see git log) |
| `b7c40b6` | (see git log) |
| `21871d1` | (see git log) |
| `786f9bb` | (see git log) |
| `3e24971` | (see git log) |
| `87176c7` | (see git log) |
| `b80484c` | (see git log) |
| `3a072fa` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: InterviewRAG 单元测试 + 体验细节修复

**Date**: 2026-06-07
**Task**: InterviewRAG 单元测试 + 体验细节修复
**Branch**: `master`

### Summary

添加后端单元测试（MD解析器13个测试+API Mock测试+Retriever测试），修复输入框发送后不清空、回答中可提前编辑等体验细节

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `af57a77` | (see git log) |
| `8d1cb79` | (see git log) |
| `28ac338` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: RAG 评估体系实现

**Date**: 2026-06-08
**Task**: RAG 评估体系实现
**Branch**: `master`

### Summary

实现完整 RAG 评估体系：RAGAS 0.4.3 集成（智谱 AsyncOpenAI + llm_factory）、检索指标（Hit Rate/MRR 关键词匹配）、回归检测（latest.json + history 归档）、CLI 入口（--mode full/ragas/comparison/sanity）、改写题目评估数据集。Baseline: faithfulness=0.667, answer_relevancy=0.717, 混合检索 HR@5=0.3529 > 纯向量 0.2353。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `dad269f` | (see git log) |
| `1c4a77e` | (see git log) |
| `485c09c` | (see git log) |
| `c8b27fc` | (see git log) |
| `003f0c1` | (see git log) |
| `158e4c2` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: RAG 评估体系 + 文档更新

**Date**: 2026-06-09
**Task**: RAG 评估体系 + 文档更新
**Branch**: `master`

### Summary

完成 RAG 评估体系：RAGAS 0.4.3 集成（智谱 AsyncOpenAI + llm_factory）、检索指标（Hit Rate/MRR 关键词匹配）、回归检测、CLI 入口、改写题目评估数据集。修正评估区分度问题（原题→改写题）。Baseline: faithfulness=0.667, answer_relevancy=0.717, 混合检索 HR@5=0.3529。更新 README 和 quality-guidelines spec。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `dad269f` | (see git log) |
| `1c4a77e` | (see git log) |
| `485c09c` | (see git log) |
| `c8b27fc` | (see git log) |
| `003f0c1` | (see git log) |
| `158e4c2` | (see git log) |
| `7fa43d4` | (see git log) |
| `0e2a6e3` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: 修复聊天/知识库 3 个 bug

**Date**: 2026-06-09
**Task**: 修复聊天/知识库 3 个 bug
**Branch**: `master`

### Summary

修复 3 个 bug：(1) SSE 流式 400 移除 response_model 避免 Pydantic 校验冲突；(2) 切走对话答案变三点 — 后端 CancelledError 捕获+前端 useRef 保存 partial；(3) 导入无效 — IngestModal onComplete 从渲染体改 useEffect+hasCompleted flag。验证：30 单测通过 + tsc + build OK。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `4edebe8` | (see git log) |
| `18eb1eb` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete

---

## Session: 2026-06-09 — unify-chat-state (P2)

### Goal
把 useConversations 状态合并进 ChatContext，消除多实例 + localStorage 竞争；useConversations 保留为 adapter。

### Planning
- [OK] prd.md / design.md / implement.md 写完（complex 任务三件套齐全）
- [OK] implement.jsonl + check.jsonl curate 完，validate 通过
  - 4 implement entries (state-management / type-safety / quality / hook)
  - 2 check entries (quality / state-management)
- [OK] 用户确认计划 + 选 sub-agent 派发模式
- [OK] task.py start → status=in_progress

### Key Facts
- Sidebar.tsx 用 `import type { Conversation }` → 改 adapter 后 type-only 兼容
- 项目无 jest/vitest 配置（package.json 无 test script）→ 测试代码可写但不一定能跑，需 sub-agent 评估
- ChatProvider 当前的 `subscribe` 仍会触发外部订阅（page.tsx 用过），合并后保留

### Implementation
- (in progress) Dispatching trellis-implement sub-agent

### Implementation
- [OK] Steps 1-5 (trellis-implement): ChatContext 合并 / useConversations adapter / 删 ConversationsBootstrap / page.tsx 简化
  - tsc 0 错误, build 成功 (5/5 pages)
  - 加 `hasHydratedRef` 防止初始空 state 覆盖 localStorage (超出 design.md 的 safety net,合理)
- [OK] trellis-check 独立验收: 5/5 必查项 + spec 合规全过
  - 唯一 PRD gap = 单测缺失 (Step 6)
- [OK] Step 6 单测 (trellis-implement): 选 vitest (无 jest 配置,装 vitest 4.1.8 + RTL + jsdom)
  - 20 tests / 4 describe 全绿 (1.32s)
  - 覆盖 implement.md §4 全部 P1 场景 + adapter 兼容性
  - tsc + build 重跑仍 0 错
- [OK] 端到端浏览器手测 (playwright MCP): 8 项验证全过
  - hydration guard / 新建 / 切路由 / 刷新恢复 / 单实例 / 多对话 / 切换 / 删除
  - console 仅 favicon 404 + 后端连接拒绝 (无关)

### Spec Updates
- [OK] `.trellis/spec/frontend/state-management.md` — 新增 "Context 持久化的反模式 → 修正模式" 章节 (含 hydration guard + adapter 模式)
- [OK] `.trellis/spec/frontend/quality-guidelines.md` — 测试框架章节从 Jest 迁到 Vitest 4 (含 oxc JSX 注意)

### Status
[OK] **Implementation + verification done**, ready for commit.

---

## Session: 2026-06-09 — eval-web-ui + markdown-streaming (父任务 06-09-eval-and-render)

### Parent task
- 06-09-eval-and-render — 评估报告 + 流式渲染下一迭代

### Child A: 评估报告 Web 页 (06-09-eval-web-ui)
- [OK] brainstorm: 数据访问=新后端 endpoint、页面模块=MVP、路由=/eval+Sidebar第3tab、详情=展开式SPA
- [OK] 实施: backend/app/api/eval.py (summary + detail 两个endpoint)，frontend /eval 页面
- [OK] 拆分 RagMetricsBar + ComparisonTable 子组件（page.tsx 从 313 行降到 151 行）
- [OK] trellis-check: 1 issue (page 313>150行)，已修复；其他 5/5 必查项全过
- [OK] 浏览器验证: /eval 页面正确显示 4 个 RAGAS 指标 + 3 策略对比表 + 4 条历史快照 + 展开交互
- [OK] commit: `2deb76d` feat(eval): 评估报告 Web 页面 + 后端 /api/eval endpoints
- [OK] archive: 06-09-eval-web-ui → archive/2026-06/

### Child B: 流式 markdown 渲染 + 代码高亮 (06-09-markdown-streaming)
- [OK] brainstorm: highlight.js + rehype-highlight，不做流式截断处理，github-dark.css 主题
- [OK] 实施: 安装 highlight.js，ChatMessage.tsx 加 rehypePlugins + CSS import（3 处改动）
- [OK] 浏览器验证: Python 快排代码块 .hljs-keyword 13个 + .hljs-string 2个
- [OK] commit: `7b8cf81` feat(chat): 接入 highlight.js 代码块语法高亮
- [OK] archive: 06-09-markdown-streaming → archive/2026-06/

### Commits (this session)
- `4b27086` refactor(chat): 统一 chat 状态到 ChatContext（上一 task）
- `2381c78` chore(task): archive 06-09-unify-chat-state（上一 task）
- `7b8cf81` feat(chat): 接入 highlight.js 代码块语法高亮
- `2deb76d` feat(eval): 评估报告 Web 页面 + 后端 /api/eval endpoints
- `chore(task): archive markdown-streaming` / `chore(task): archive eval-web-ui` / `chore(task): archive eval-and-render`


## Session 6: 统一 chat 状态 + 高亮 + 评估页面 + ESLint + 安全修复 + Spec

**Date**: 2026-06-09
**Task**: 统一 chat 状态 + 高亮 + 评估页面 + ESLint + 安全修复 + Spec
**Branch**: `master`

### Summary

6 个功能任务: ChatContext 统一状态消除多实例竞争; highlight.js 代码高亮; /eval 评估报告 Web 页面+后端 endpoint; ESLint 8 接入; P0/P1 安全漏洞修复(路径遍历/CORS/asyncio import/并发竞争); 后端安全规范 spec。项目健康度 6.5→8/10。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `4b27086` | (see git log) |
| `7b8cf81` | (see git log) |
| `2deb76d` | (see git log) |
| `371ee1a` | (see git log) |
| `da6073b` | (see git log) |
| `84dbc5a` | (see git log) |
| `bb52c53` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete

## Session 7: 项目状态盘点 + 小事收尾 (2026-06-10)

**Task**: 阶段性盘点 — 看看下一步做什么
**Branch**: `master`

### 状态盘点

项目健康度 ≈ 8/10。近 30 个 commit 全部合入 master,主线功能完整:
- RAG Pipeline(混合检索 + Small-to-Big + BGE Re-ranker)
- RAGAS 0.4.3 集成 + baseline(faithfulness=0.667, answer_relevancy=0.717)
- 评估 Web UI(`/eval`) + highlight.js 代码高亮
- ChatContext 状态统一(20 个 Vitest 单测) + hydration guard
- ESLint 8 接入(0 warnings) + P0/P1 安全修复(路径遍历/CORS/asyncio/并发)
- 后端 8 个 pytest 文件;前端 20 个测试

### 下一步候选(已和用户讨论)

| 方向 | 价值 | 建议 |
|---|---|---|
| **A 质量门禁:CI + 测试补全** | 高(防 P0 回归) | **下次会话主推** |
| B BGE Re-ranker Windows 卡死 | 中(运维向) | 看时间 |
| C RAG 调参 + 检索改写 | 中(数据向) | 评估体系已就位 |
| D 端到端性能埋点 | 中 | 门槛低 |
| E 鉴权/RBAC | 低(单用户 demo) | 部署再说 |

**用户拍板**:下次会话优先做 **A(质量门禁:CI + 测试补全)**,本次只做小事收尾。

### 本次收尾(3 件事)

1. **补 .gitignore**(根):
   - `.codegraph/daemon.pid` — 本机 daemon 进程 ID,不该进 git
   - `*.tsbuildinfo` — TS 增量编译缓存,任何 Node 项目都该忽略
   - `.trellis/.template-hashes.json` / `.trellis/.version` — Trellis 本地状态
   - `.codex/` / `.agents/` — agent runtime 目录,本机工具非项目源码
2. **`git rm --cached`** 4 个之前误 tracked 的本机状态文件(保留工作区副本):
   - `.codegraph/daemon.pid`、`.trellis/.template-hashes.json`、`.trellis/.version`、`frontend/tsconfig.tsbuildinfo`
3. **journal 本条记录**(就是这一段)

### 验证

`git status` 现状:仅 `.gitignore` 修改 + 4 个 D(delete-from-index) + 0 个 untracked。干净。

### 留给下次会话的入口

直接新建 Trellis 父任务 `06-10-ci-coverage`,子任务:
- 子 1:`.github/workflows/ci.yml` — 后端 pytest + 前端 vitest + ESLint + (可选) build
- 子 2:后端高风险模块补 Vitest(path_guard / ingest / query SSE 流式 partial)
- 可选子 3:pre-commit hook(本地质量门禁)

### Status

[OK] **收尾完成**,工作区干净,等下次会话开 Trellis 任务。

### Next Steps

- 下次会话:开 `06-10-ci-coverage` 父任务,优先做 CI workflow

## Session 8: CI 接入完成 (2026-06-10 晚)

**Task**: 06-10-ci-coverage 质量门禁
**Branch**: `master`

### 完成内容

1. **CI Workflow**: `.github/workflows/ci.yml` — push/PR 到 master 触发
   - 后端 pytest (98 tests) + coverage (52%)
   - 前端 vitest (20 tests) + ESLint (0 warnings) + build
   - 前端 coverage (60% statements)
   - 三 job 并行,3 分钟完成
2. **测试修复**:
   - `test_api.py`: test_query_with_history 断言修复(mock list 引用问题)
   - `test_questions_api.py`: 新增 `_isolate_db` autouse fixture(临时 SQLite 隔离)
   - `questions.py`: ChromaDB 异常改为 HTTPException(500)
3. **依赖补全**:
   - `requirements.txt`: 加 `pytest-cov==6.1.1`
   - `package.json`: 加 `@vitest/coverage-v8`
4. **CI 环境配置**:
   - `conftest.py`: `ZHIPU_API_KEY=test-key` 防止 CI 502 崩溃
5. **Branch Protection**: GitHub 设置完成
   - master 分支必须通过 CI 才能合并 PR
   - 三个 status check 必须全部绿灯

### CI 调试经验

- `pytest-cov` 和 `@vitest/coverage-v8` 是 coverage 必需依赖,不显式装会报 `unrecognized arguments`/`MISSING DEPENDENCY`
- CI 没有 `.env` 文件,RAGService 初始化需要 API key,用 `os.environ.setdefault` 提供后备
- `--cov=app` 需要设置 `PYTHONPATH=.` 让 pytest 正确 import

### Git 学习

- 学会了 SSH key 配置(push 到 GitHub)
- GitHub 443 端口绕过 GFW(SshConfig 设 `HostName ssh.github.com`)

### Next Steps

- 独立任务: `06-10-backend-tests` — 补 path_guard / query SSE / ingest 高风险模块测试
- 或: RAG 调参 — 用评估体系做检索参数扫描
