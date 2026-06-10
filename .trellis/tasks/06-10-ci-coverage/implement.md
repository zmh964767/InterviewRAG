# Implement — 质量门禁:CI + 测试补全

> 配套 PRD: `prd.md` / Design: `design.md`(同目录)

## 0. 前置确认(任务开始前必做)

- [ ] 0.1 本任务目录存在:`.trellis/tasks/06-10-ci-coverage/{prd,design,implement}.md` 齐全
- [ ] 0.2 仓库工作区干净(`git status` 不应有未提交的非本任务改动)。本次收尾的 `.gitignore` + journal + 4 个 `git rm --cached` 文件**应已 commit**(或本任务一并提交)
- [ ] 0.3 用户已 review 三件套并明示放行

> 任务开始前先 `git status` 看一下,如有非本任务的 dirty 文件,**先 commit 或 stash**。

## 1. 实施步骤(严格按序)

### Step 1. 本地预跑(必须全过)

```bash
# 后端(⚠️ 本机装 pytest 9.0.3,CI 按 requirements.txt 装 8.3.0,若有 deprecation warning 先修)
cd backend
python -m pip install -r requirements.txt
pytest --maxfail=1 -q
# 期望:全绿,无 warning
# ⚠️ conftest.py 直接 import app.main — 若因无 ChromaDB/智谱配置报错,需在此步修 mock
```

**这一关过不去不进入 Step 2**。若某条红:
- 后端测试红 → 看 failure trace,fix 后再跑
- `conftest.py` import app 失败 → 是 ChromaDB 初始化副作用,需在 conftest 里加 `autouse` fixture mock 掉 `vectorstore` 初始化(具体 mock 方式看报错)
- ESLint 红 → `npm run lint -- --fix` 自动修;手动修剩余
- build 红 → 一定是 TS 类型错,看 error 行修

### Step 2. 创建 CI workflow 文件

新文件:`.github/workflows/ci.yml`

完整内容见 `design.md` §3.1(YAML 已草拟),要点:
- `on.push.branches: [master, main]`
- `on.pull_request.branches: [master, main]`
- `concurrency` 取消过时 run
- 三个 job:`backend-tests` / `frontend-tests` / `frontend-build`
- 后端 job 设 `env: SKIP_RERANKER: "1"`
- 后端装依赖用 `cache: pip` + `cache-dependency-path: backend/requirements.txt`
- 前端装依赖用 `cache: npm` + `cache-dependency-path: frontend/package-lock.json`
- `timeout-minutes: 10`
- coverage 上报用 `actions/upload-artifact@v4`

写入命令:

```bash
mkdir -p .github/workflows
# 用 Write 工具创建 .github/workflows/ci.yml
```

### Step 3. 验证 YAML 语法(可选)

```bash
# GitHub Actions 会直接拒绝 bad YAML,本地验证是 extra safety
# 如已装 PyYAML:
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml').read())" && echo "YAML OK"
# 如没装 PyYAML,跳过此步(在 GitHub 端验证即可)
```

### Step 4. 提交并 push

```bash
git add .github/workflows/ci.yml
git status          # 应只显示 ci.yml
git diff --cached   # review
git commit -m "ci: 接 GitHub Actions — 后端 pytest + 前端 vitest/lint/build

- 新增 .github/workflows/ci.yml
- push/PR 到 master/main 触发
- 后端 job 设 SKIP_RERANKER=1 绕 BGE 卡死
- coverage 仅信息上报,无门槛
- 严格门禁,任何 step 红 = 整个 run 红"
git push origin master
```

### Step 5. 在 GitHub 端验证

- [ ] 5.1 打开 repo 的 Actions 标签页,确认新 workflow 出现并跑通 ✅
- [ ] 5.2 点进 run,确认三个 job 全部绿
- [ ] 5.3 下载 coverage Artifact,确认能解压看到 `coverage.xml` / `coverage/index.html`
- [ ] 5.4 总耗时 < 10 分钟(无 build)/ < 15 分钟(含 build)
- [ ] 5.5 (可选)故意开一个空 commit 提个测试 PR,确认 CI 在 PR 上也跑(然后 close)

### Step 6. (可选)把本 PR 合入 master

仅当 GitHub 端 CI 全绿 + 验收清单(见 §2)全过时合入。

## 2. 验收清单(对照 prd AC)

| AC | 验证方式 | 通过条件 |
|---|---|---|
| AC1 | GitHub Actions 在 PR 上跑,任何 step 红 = 红 | 提测试 PR 看到红,改回绿 |
| AC2 | workflow 文件含 `SKIP_RERANKER: "1"` | grep 验证 |
| AC3 | 单次 < 10 min / 含 build < 15 min | Actions 标签页显示时间 |
| AC4 | `cd backend && pytest` 全绿 | Step 1 |
| AC5 | `npm test` 20/20 全绿 | Step 1 |
| AC6 | `npm run lint` 0 warning | Step 1 |
| AC8 | coverage artifact 可下载 | Step 5.3 |
| AC9 | Actions 标签出现并显示成功 | Step 5.1 |

## 3. 风险点与回滚

| 风险 | 触发 | 缓解 / 回滚 |
|---|---|---|
| `pip install` 装 `sentence-transformers` 失败 | 网络不稳 / 编译失败 | 加 `pip install --prefer-binary`;若仍失败,`cache: pip` 通常能解 |
| `npm ci` 报 lock 与 package.json 不一致 | 本地 lock 旧 | `rm package-lock.json && npm install && git add package-lock.json` |
| `npm run build` 报 TS 类型错 | 与 `npm run dev` 路径有差异 | 看 build error 行修,可能需要 `next.config.mjs` 调整 |
| CI runner 跑 15+ 分钟 | 极端情况 | 加 `timeout-minutes: 10` 已设,会强制 kill;可调短 |
| 提交后 push 失败,本地 dirty 漏掉 | workflow 文件 + 之前 dirty 混在一起 | commit 前 `git status` 必须只显示 `.github/workflows/ci.yml` |

**回滚**:
- workflow 是新文件,删 `.github/workflows/ci.yml` 一次 commit 即可回滚
- 不会影响任何代码或测试,零破坏

## 4. 提交规范

- commit 类型:`ci:`(约定式)
- 标题:`ci: 接 GitHub Actions — 后端 pytest + 前端 vitest/lint/build`
- body 见 Step 4

## 5. Spec 更新 — 不在本任务 AC 范围

Spec 更新推迟到 `06-10-backend-tests` 任务统一写一次,避免本次"半外移"。本次 journal 追加 Session 8 即可。

- [ ] 在 `journal-1.md` 追加 Session 8 记录本次 CI 接入(收尾 commit)

## 6. 后续(本次外)

- 独立任务 `06-10-backend-tests`(本次不创建,见 prd Q1/Q2 已结)
- (可选)GitHub branch protection 规则
- (可选)Dependabot / pre-commit hook
