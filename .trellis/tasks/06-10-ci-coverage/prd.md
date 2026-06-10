# 质量门禁:CI + 测试补全

## Goal

为 InterviewRAG 接入持续集成门禁,把"安全修复 + 测试补全"这一波工作**固化为自动检查**,防止下次 PR/Push 退化(路径遍历、CORS、并发竞态、误改 `requirements.txt` 等)。覆盖后端 pytest + 前端 vitest + 前端 ESLint,作为后续所有 PR 的最低质量门槛。

## Background / 为什么做

- 2026-06-09 Session 6 集中修了一波 P0/P1 安全漏洞(`path_guard` / CORS / asyncio import / 并发),但**没有自动守门**,下次再被改回去没人知道。
- 当前 `.github/` 目录不存在 — 项目从未接入过 CI,所有质量检查都是手跑。
- 后端 8 个 pytest 文件已就位(`backend/tests/`),前端 20 个 vitest 测试已就位 — **测试不是 0,是 0 自动触发**。
- 后端几个高风险模块(`path_guard`、`ingest_service`、`query` 的 SSE 流式 partial 同步)测试覆盖密度尚未在安全审查里量化,本次可借机补一轮。

## Confirmed Facts(已查证)

| # | 事实 | 来源 |
|---|---|---|
| 1 | `.github/` 目录不存在,从未接入 CI | `ls .github/` |
| 2 | 后端已有 8 个 pytest 文件,含 `conftest.py`、`test_path_guard.py`、`test_api.py`、`test_questions_api.py` 等 | `backend/tests/` |
| 3 | 前端 vitest 4 + RTL + jsdom,`package.json` 有 `test` / `lint` / `build` 三个 script | `frontend/package.json` |
| 4 | 本机已装 pytest 9.0.3 / fastapi 0.136.3;但 **CI 会按 `requirements.txt` 安装 pytest 8.3.0 + fastapi 0.115.0**。可能存在 deprecation 差异。 | `pip show` + `cat requirements.txt` |
| 5 | `.trellis/spec/{backend,frontend}/quality-guidelines.md` 已存在,定义 lint/format/测试规范 | ls .trellis/spec |
| 6 | 评估 `--mode ragas` 一次 ~30 分钟,**不适合 CI**;`SKIP_RERANKER=1` 必须在 CI 设 | memory `ragas-evaluation-setup.md` |
| 7 | journal Session 7 已记录本任务入口 | `.trellis/workspace/zerobyheart/journal-1.md` |
| 8 | `conftest.py` 直接 `from app.main import app` → import 会触发 ChromaDB/智谱等 service 初始化。现有测试用 mock 绕过,**CI 上必须验证不依赖网络/外部服务,否则需加 mock** | `backend/tests/conftest.py` |

## Requirements(待 prd 终稿确认)

### MUST
- R1. GitHub Actions workflow 文件,触发条件 = `push` 到 master/main + `pull_request` 到 master/main(用户已确认 push + PR 都触发)
- R2. workflow 至少跑:后端 pytest + 前端 vitest + 前端 ESLint
- R3. CI 环境必须 `SKIP_RERANKER=1`(Windows BGE 卡死的唯一稳定绕开方式)
- R4. CI 不跑 RAGAS 评估(成本太高),仅跑单测
- R5. 一次失败 = CI 红 = 不可 merge(默认 GitHub 行为,用户已确认严格门禁)
- R6. workflow 用免费 runner(`ubuntu-latest`),不在 CI 跑 Windows-only 的 Re-ranker

### SHOULD(默认纳入,用户已确认 MVP 范围)
- R7. 前端 `npm run build` 也跑一遍(防 TS 编译通过但 build 失败)
- ~~R8. 后端高风险模块补一轮 Vitest(等同 pytest)覆盖:`path_guard` 全部分支、`query` 的 SSE cancelled/partial 路径、`ingest` 的 md/pdf/web 三类解析~~ → **用户拍板:留到下次独立子任务**
- R9. coverage 上报(`pytest-cov` + `vitest --coverage`),**仅作为信息**,不设硬门槛(避免 noise)
- R10. workflow 加 `concurrency` 字段取消过时 run、设 `timeout-minutes`

### COULD(可选)
- R11. 加 pre-commit hook(本地钩子,在 commit 前跑 lint/format)
- R12. 加 Dependabot/renovate 自动依赖更新
- R13. backend Dockerfile / docker-compose 烟测

## Acceptance Criteria(可测试)

- [ ] AC1. PR 提到 master/main 时,GitHub Actions 必跑后端 pytest + 前端 vitest + 前端 ESLint;任一红 = 红 ❌
- [ ] AC2. CI 环境变量含 `SKIP_RERANKER=1`,跑后端单测无 BGE 加载卡死
- [ ] AC3. CI 单次运行时间 < 10 分钟(不含 build);含 build < 15 分钟
- [ ] AC4. 后端单测本地 `cd backend && pytest --maxfail=1 -q` 仍 100% 通过(零回归;跑全部 `backend/tests/test_*.py` 8 个文件)
- [ ] AC5. 前端单测 `npm test` 仍 100% 通过
- [ ] AC6. 前端 ESLint `npm run lint` 仍 0 warnings/errors
- [ ] ~~AC7. (若纳入 R8)新增的后端高风险模块测试全绿~~ → R8 已外移
- [ ] AC8. (若纳入 R9)CI 步骤产出 coverage 摘要,可在 PR 评论/Artifact 查看
- [ ] AC9. workflow 文件提交后,GitHub 端 Action 标签出现并显示成功 ✅

## Out of Scope(明确不做)

- RAGAS 评估接入 CI(成本太高,30 分钟/次,改在本地按需跑)
- BGE Re-ranker Windows 卡死根治(单独立项,不在本次)
- 鉴权/RBAC(单用户 demo,部署再说)
- 性能埋点 / SLO
- Docker 镜像发布 / 自动部署

## Open Questions(阻塞规划)

- ~~Q1. Scope 边界~~ → ✅ **MVP = 仅 CI workflow(后端 pytest + 前端 vitest + 前端 ESLint + 前端 build + coverage)**,后端补测拆给下次独立子任务 `06-10-backend-tests`。
- ~~Q2. 子任务拆分粒度~~ → ✅ **拆为两个独立 Trellis 任务**:`06-10-ci-coverage`(本任务,仅 CI workflow) + `06-10-backend-tests`(另起,补 `path_guard` / `query` SSE / `ingest` 测试)。本次不创建 `06-10-backend-tests`,仅记录入口。
- ~~Q3. CI 触发矩阵~~ → ✅ **push 到 master/main + PR 到 master/main 都触发**(用户已确认)。
- ~~Q4. 失败容忍度~~ → ✅ **严格门禁**(用户已确认)。workflow 任何 step 红 = 整个 run 红。合入本 PR 前,需在本地 `cd backend && pytest` + `cd frontend && npm test` + `npm run lint` 全部 0 错。
- ~~Q5. 补测模块优先级~~ → ✅ **已外移到独立任务 `06-10-backend-tests`**,不再阻塞本任务。

## Notes

- 范围决策直接影响 `design.md` 长度;Q1/Q2 确认前不写 design。
- 复杂度 = 中等;按 Trellis 复杂任务标准,三件套齐备再 `task.py start`。
- 本任务与 `.trellis/spec/backend/quality-guidelines.md` / `.trellis/spec/frontend/quality-guidelines.md` 强相关,落成 spec 时优先复用既有规则,不另立规范。
- 独立任务 `06-10-backend-tests` 本次不创建,仅在 journal / 下次会话起 task 时引用。
