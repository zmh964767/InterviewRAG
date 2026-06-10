# Design — 质量门禁:CI + 测试补全

> 配套 PRD: `prd.md`(同目录)

## 1. 范围

本任务 = **仅 CI workflow**。后端高风险模块补测拆给独立任务 `06-10-backend-tests`,本次不创建。

CI workflow 必须:

1. 后端 `pytest`(含当前 8 个测试文件)
2. 前端 `vitest run`(20 个测试)
3. 前端 `next lint`(ESLint 8)
4. 前端 `next build`(防 TS 编译通过但 build 失败)
5. 后端 coverage + 前端 coverage 上报(信息性,不设门槛)

## 2. 架构与边界

```
仓库根
├── .github/
│   └── workflows/
│       └── ci.yml            # 新增:CI 主流程
├── backend/                  # 不动
│   ├── requirements.txt      # 不动(已含 pytest==8.3.0 + pytest-asyncio==0.24.0)
│   ├── app/
│   └── tests/                # 不动
└── frontend/                 # 不动
    ├── package.json
    └── vitest.config.ts
```

**新文件清单**(本次只新增 1 个):

| 路径 | 用途 |
|---|---|
| `.github/workflows/ci.yml` | CI 主流程(后端 + 前端),push/PR 到 master/main 触发 |

**不动**:`backend/requirements.txt`、测试源码、frontend 任何文件(避免本次意外回归)。

## 3. 数据流与契约

### 3.1 CI workflow 结构

```yaml
name: CI

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      SKIP_RERANKER: "1"          # R3:Windows BGE 卡死的唯一稳定绕开
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - working-directory: backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - working-directory: backend
        env:
          PYTHONPATH: .
        run: |
          pytest --maxfail=1 --tb=short -q \
            --cov=app --cov-report=term-missing --cov-report=xml
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: backend-coverage
          path: backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - working-directory: frontend
        run: npm ci
      - working-directory: frontend
        run: npm run lint
      - working-directory: frontend
        run: npm test -- --reporter=verbose --coverage
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: frontend-coverage
          path: frontend/coverage

  frontend-build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    # 不依赖 frontend-tests,三 job 完全并行;lint 红不影响 build 判定,两者同时失败也只各报各的
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - working-directory: frontend
        run: npm ci
      - working-directory: frontend
        run: npm run build 2>&1 | tee build.log
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: frontend-build-log
          path: frontend/build.log
```

> **设计说明**(补充):
> - **三 job 完全并行**:`backend-tests` / `frontend-tests` / `frontend-build` 均无 `needs`,同时跑。`frontend-build` 不等 `frontend-tests`。
>   理由:两者各跑各的 lint / build 失败,失败是并行的,不会浪费 runner;而且"lint 红就不 build"没有实际收益——两者独立是更干净的并行,总墙时间 = max(三 job) ≈ 3 分钟。
> - **`frontend-build` 失败时上传 `build.log`**:用 `tee` 捕获 `2>&1` 输出,artifact 只传日志文件(不含不完整的 `.next/` 目录)。
> - **`backend-tests` 的 `PYTHONPATH: .`** 已设,确保 `from app.main import app` 正确解析。
> - **`conftest.py` 有网络副作用风险**:`from app.main import app` 会触发 ChromaDB 初始化。若 CI 端运行时因"无 ChromaDB 数据目录"报错,需在 `conftest.py` 或 CI 侧加 fixture mock。已列入 Confirmed Facts #8,Step 1 本地预跑时要验证。

### 3.2 并行性

- `backend-tests`、`frontend-tests`、`frontend-build` **三个 job 完全并行**(均无 `needs`)
- **墙时间** ≈ max(后端 ~3min, 前端 lint+test ~2min, 前端 build ~1min) ≈ **3 分钟**,远低于 AC3 < 10 min
- `frontend-build` 不等 `frontend-tests` 的理由:两者失败各自报告,不浪费 runner;三并行墙时间最短

### 3.3 失败行为(严格门禁,用户已确认)

- 任一 job 失败 → workflow 红
- GitHub 默认 branch protection(若启用)会拦 PR 合并
- 本次合入该 PR 时,需在本地先确保三件套全过(否则 PR 上 CI 直接红)

## 4. 关键决策与权衡

| 决策 | 选 | 理由 | 备选 |
|---|---|---|---|
| Runner | `ubuntu-latest` | 免费、sentence-transformers 在 Linux 上比 Windows 快 | windows-latest(成本高且 BGE 卡死) |
| Python 版本 | `3.11` | 用户已确认;兼容 `contextlib.asynccontextmanager`、业界 LTS 习惯 | 3.10(更老但稳)、3.12(更新) |
| Node 版本 | `20.x` | Next.js 14 推荐 | 18(Next 14 也支持,但 20 是 LTS) |
| 后端 cache | `cache: pip` + `cache-dependency-path: backend/requirements.txt` | 装 sentence-transformers 第一次 2~3 min,缓存后 30s | 不缓存(每次重装,慢) |
| 前端 cache | `cache: npm` + `cache-dependency-path: frontend/package-lock.json` | 标准做法 | 不缓存 |
| 失败容忍 | 严格门禁 | 用户已确认 | continue-on-error(被否) |
| RAGAS | 不跑 | 30 分钟/次,免费额度烧不起 | 跑(成本爆炸) |
| Re-ranker | `SKIP_RERANKER=1` | Windows BGE 卡死的唯一稳定绕开 | 不跳过(在 Linux 也不需要,但留这个环境变量更稳) |
| 后端 maxfail | `--maxfail=1` | 第一个红就停,节省时间 | 默认(会跑完) |

## 5. 兼容性 / 迁移 / 风险

### 5.1 与现有 spec 的关系

- `.trellis/spec/backend/quality-guidelines.md` / `.trellis/spec/frontend/quality-guidelines.md` **本次不改**——Spec 更新是独立可选工作,不在本任务 AC 范围。留到 `06-10-backend-tests` 统一写一次。

### 5.2 已知风险

| 风险 | 触发场景 | 缓解 |
|---|---|---|
| `pip install` 装 `sentence-transformers` 失败 | 网络 / 依赖编译 | cache: pip 大概率解决首次;若失败改 minimal install |
| `npm ci` 失败 | lock 与 package.json 不一致 | 本地 `npm install` 修 lock |
| `next build` 报 SSR 错误 | 当前 `npm run dev` 跑通但 build 路径有差异 | 跑 `npm run build` 本地预过(见 AC4~6) |
| ChromaDB 初次 init 慢 | CI 首次 | 不跑集成测试(只看单元) |
| `python import app` 失败 | CI 装了 deps 但没设 `PYTHONPATH` | workflow 里显式 `env: PYTHONPATH: .` |
| 触发 push 时 commit 没 push 干净 | 容易忽略的本地 dirty 路径 | 本任务不引入,留给后续 |

### 5.3 不在本次做

- 写 spec(留到 `06-10-backend-tests` 统一写)
- 设 GitHub branch protection(需要 repo admin 权限,GitHub UI 操作)
- 触发 `master`(branch)改为 `main` — 项目用 master,workflow 兼容两者
- pre-commit hook(R11)
- Dependabot(R12)

## 6. 用户已确认的小决策

- ✅ **Python 版本 = 3.11**(用户已确认)
- ✅ **coverage = 仅信息上报,无门槛**(用户已确认)

## 7. 验证

| 步骤 | 命令 | 期望 |
|---|---|---|
| 本地后端 | `cd backend && pytest --maxfail=1 -q` | 全绿 |
| 本地前端单测 | `cd frontend && npm test` | 20/20 全绿 |
| 本地前端 lint | `cd frontend && npm run lint` | 0 warnings |
| 本地前端 build | `cd frontend && npm run build` | 成功 |
| 提交后 | push to master | GitHub Action 标签出现并跑通 |
| PR 验证 | 提一个故意红的小 PR | CI 红 ❌,改回绿后 ✅ |

## 8. 后续(本次外)

- 独立任务 `06-10-backend-tests`:补 `path_guard` / `query` SSE / `ingest` 三类解析的测试
- 写 spec:`.trellis/spec/{backend,frontend}/quality-guidelines.md` 追加 CI 触发矩阵章节
- (可选)branch protection 规则
