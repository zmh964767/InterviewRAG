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
