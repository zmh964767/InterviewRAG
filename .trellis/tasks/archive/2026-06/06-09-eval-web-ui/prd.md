# 评估报告 Web 页

## Goal

把当前 `cat backend/evaluation/report.md` 的命令行流程,改造成一个 Web 页面:浏览器打开 `/eval` 就能看到最新一次评估 + 历史快照,无需切到终端。

## Confirmed Facts(来自代码)

### 后端评估产物已就位
- `backend/evaluation/results/latest.json` — 最新一次完整结果(aggregated + comparison + total + errors)
- `backend/evaluation/results/latest_summary.json` — 简化版(metrics / error_count / total / timestamp)
- `backend/evaluation/results/history/2026-06-08T23-26-02.json` 等 4 个 — 历史快照(ISO 时间戳文件名)
- `backend/evaluation/report.md` — 由 `reporter.py` 生成的 markdown 报告

### 现有数据形状(latest.json)
```json
{
  "aggregated": { "faithfulness": 0.6667, "answer_relevancy": 0.7169,
                  "context_precision": 1.0, "context_recall": 1.0 },
  "errors": [],
  "total": 17,
  "comparison": {
    "A_纯向量": { "hit_rate@5": 0.2353, "mrr": 0.2353 },
    "B_混合检索": { "hit_rate@5": 0.3529, "mrr": 0.2794 },
    "D_小块检索大块生成": { "hit_rate@5": 0.2353, "mrr": 0.2353 }
  }
}
```

### 历史快照形状(latest_summary.json 结构, history/<ts>.json 同)
```json
{
  "metrics": { ... },
  "error_count": 0,
  "total": 17,
  "timestamp": "2026-06-08T23:26:02"
}
```

### 当前前端
- Sidebar 已有 2 个 tab: "对话" / "知识库" → 要加第 3 个 "评估"
- 路由: `/`(对话) / `/kb`(知识库) → 要加 `/eval`(评估)
- 现有所有数据过 `lib/api.ts` → 后端需新增 endpoint

### 后端现有端点(不新增)
- `POST /api/query` — 问答(SSE)
- `GET /api/health` / `GET /api/stats`
- `GET /api/questions` — 题目列表
- 无评估相关的 endpoint

---

## Scope

### 决策记录
1. **数据访问**: 新后端 endpoint `/api/eval/summary`,聚合 latest + history + count(用户确认)
2. **页面模块**: MVP — 顶部 latest 一次性表 + 历史快照列表 + 单次详情(用户确认)
3. **路由 + 入口**: `/eval` 顶级路由 + Sidebar 第 3 个"评估"tab(用户确认)

### In Scope

#### 后端
- [ ] `GET /api/eval/summary` — 读取 `evaluation/results/latest_summary.json` + 扫描 `history/*.json` 排序返回
- [ ] `GET /api/eval/detail?ts=<ISO>` — 读取指定历史快照的完整 JSON(无 ts 时返回 latest)
- [ ] **不加**触发运行的端点

#### 前端
- [ ] `/eval` 路由页面 `app/eval/page.tsx`
- [ ] Sidebar 第 3 tab "评估"(`pathname.startsWith('/eval')`)
- [ ] 顶部 latest 一次性表:
  - RAGAS 4 指标数字 + 每项条形/色块
  - 检索策略对比表(A/B/D 的 Hit Rate@5 + MRR)
  - 成功/失败/总计
- [ ] 历史快照列表:按时间倒序,显示 timestamp + total + 错误数
- [ ] 点历史条目 → 跳转详情(或展开,待定),显示该快照的完整 latest.json
- [ ] `lib/api.ts` 加 `getEvalSummary()` + `getEvalDetail(ts?)`

### Out of Scope
- ❌ 在 Web 页触发评估运行(后端跑 30 分钟 + 需要 ZHIPU_API_KEY)
- ❌ 编辑评估数据集
- ❌ 折线图趋势(可后续加)
- ❌ 最高/最低/平均汇总(可后续加)
- ❌ 部署优化(开发阶段本地文件访问 OK)

---

## Acceptance Criteria

- [ ] `GET /api/eval/summary` 返回 `{ latest: { metrics, total, timestamp, error_count }, history: [...] }`
- [ ] `GET /api/eval/detail` 返回完整 aggregated + comparison + errors + total
- [ ] `/eval` 页面打开后 5 秒内显示 latest 一次性表(不用加载动画除非 fetch 失败)
- [ ] 点击 Sidebar "评估" tab 切到 `/eval`;对话/知识库/评估三个 tab 切换不丢失各自状态
- [ ] 历史快照列表有 4 个条目(现有),按时间倒序排列
- [ ] 点击某历史条目 → 该快照的 4 个 RAGAS 指标 + 检索策略表都正确显示
- [ ] 类型安全: `lib/types.ts` 里有 `EvalSummary` / `EvalDetail` 接口;无 `any`
- [ ] `npm run build` 成功
- [ ] 现有 `/` 和 `/kb` 不受影响

## Notes

- Active task: `.trellis/tasks/06-09-eval-web-ui` (parent: `06-09-eval-and-render`)
- 这是子任务 A;子任务 B 是"流式 markdown 渲染优化"
- 后端 endpoint 读 `evaluation/results/` 目录(仓库内相对路径,可测)
- frontend 的 `lib/types.ts` 要扩
