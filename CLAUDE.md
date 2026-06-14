# InterviewRAG 项目宪法

> Claude Code 进入本项目必读的"宪法"——所有约定按本文档执行。

---

## 1. AI 工作流硬约束

**接到"改 / 加 / 删 / 排查 / 优化 X"任务时，**先**做以下 3 步**：

1. `codegraph_impact("X")` — 看影响面（哪些文件 / 函数会被牵连）
2. `codegraph_callers("X")` — 看所有调用方
3. `codegraph_explore("X 相关概念")` — 拿源码 + 调用链

**只在以下情况跳过**：
- 改的是纯配置（YAML / JSON / ENV / `.env`）
- 改的是测试 fixture 或 mock 数据
- 改的是 docstring / 注释 / 文档
- 改的是 gitignore / 路径配置

**为什么**：CodeGraph 已经在 MCP 里可用，是项目代码知识图谱。它能秒级给跨文件调用链、影响面，**比 Read + Grep 高效 10x**。**当用则用**。

---

## 2. 工具选择优先级

| 场景 | 工具 |
|------|------|
| 单文件深读（已知路径） | Read |
| 字符串 / 标识符搜索 | Grep |
| 文件查找（glob pattern） | Glob |
| 跨文件调用链 / 影响分析 | **CodeGraph**（首选） |
| 大范围代码理解（多文件多概念） | Agent(Explore) |
| 单符号详情 | **CodeGraph**（`codegraph_explore`） |

**默认行为**：能用 CodeGraph 就不退化到 Read+Grep。

---

## 3. Trellis 工作流

项目使用 Trellis 任务管理（`.trellis/`）：

| 触发 | 命令 |
|------|------|
| 继续当前任务 | `/trellis:continue` |
| 完成任务 | `/trellis:finish-work` |
| 接到新需求 | `/trellis:continue` → 走 Brainstorm 路径 |

**完成实施后必须**：
- 跑 `pytest tests/ evaluation/tests/ -m "not eval"` 全绿
- `frontend tsc --noEmit` 无错
- spec 沉淀（新增/更新 `.trellis/spec/` 相关文件）

---

## 4. 项目特殊约束

| 约束 | 说明 |
|------|------|
| **后端默认 dev 模式** | 用 `cd backend && uvicorn app.main:app --reload`，不每次跑 Docker（Docker 镜像可能过期） |
| **Windows 上不启 BGE-Reranker** | `BAAI/bge-reranker-base` 在 Windows + Python 3.13 segment fault（exit 139），等 Linux 部署时启用 |
| **不要提交 `.env`** | 已加 .gitignore |
| **commit body 写明** | 第一行 ≤ 50 字符 summary，下面空一行 + 详细列表 |

---

## 5. 跑评估的命令

```bash
# Comparison（5-8 分钟，纯检索，0 错误）
cd backend && python -m evaluation.run --mode comparison --skip-regression

# 跑全量 RAGAS（254 题约 2-3 小时，智谱限流 60/min）
# 仅 Linux / 部署到服务器时跑，Windows 不跑
cd backend && python -m evaluation.run --mode ragas --skip-regression
```

**日常开发不要跑 RAGAS**——comparison 足够验证 BGE Reranker 效果。

---

## 6. Spec 文件位置

| 类型 | 位置 |
|------|------|
| 后端规范 | `.trellis/spec/backend/*.md` |
| 前端规范 | `.trellis/spec/frontend/*.md` |
| 设计思考 | `.trellis/spec/guides/*.md` |

新增合约变更**必须**更新对应 spec，否则后续 review 会 fail。

---

## 7. Memory 文件

项目级 memory 位置：`~/.claude/projects/D--Zerobyheart-InterviewRAG/memory/`

- 沉淀非显然知识（如"Windows 上 BGE segment fault"）
- 不写"代码已经记录的"（git history、CLAUDE.md 已有）
- 用 `[[name]]` 链接相关条目
