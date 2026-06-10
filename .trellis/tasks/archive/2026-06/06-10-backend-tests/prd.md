# 后端高风险模块补测试

## Goal

补上 `stream_generator`（SSE 流式）和 `IngestService`（多源导入）两个零测试模块的单元测试，把后端覆盖率从 52% 提高到 ~70%，让 CI 绿灯更有含金量。

## Background / 为什么做

- `path_guard.py` 已经全覆盖(5 分支/8 用例)，**不在本次范围**。
- `query.py` 的 `stream_generator` 是**零测试**：正常流式、`CancelledError` 保存 partial answer、异常分支全部空白。
- `ingest_service.py` 7 个公开方法（md/pdf/url/json + `_ingest_questions` 去重/异常/批次写入）全部**零测试**。
- 上一轮 CI 修复说明：这两个模块是安全修复重点（P0 路径遍历已覆盖，P1 CancelledError 和导入竞态还没覆盖）。

## Confirmed Facts(已查证)

| # | 事实 | 来源 |
|---|---|---|
| 1 | `path_guard.py` 5 分支已全覆盖，**排除本次** | `test_path_guard.py` 8 用例 |
| 2 | `query.py stream_generator` 3 分支：正常完成 / CancelledError / 异常 yield error SSE | `app/api/query.py` L80-135 |
| 3 | `test_api.py` 只测了 `stream=False` 的 4 个用例，SSE 零覆盖 | `backend/tests/test_api.py` |
| 4 | `ingest_service.py` 7 个公开方法 + `_ingest_questions` 去重/异常逻辑，全部零测试 | `backend/tests/` 无 ingest 相关文件 |
| 5 | `conftest.py` 已有 `_ensure_rag_service_safe`（CI 不崩），`_isolate_db` autouse（SQLite 隔离） | `backend/tests/conftest.py` |
| 6 | 现有 `test_questions_api.py` 的 `insert_one` 测试已验证 IngestService 在 SQLite 写入端的 happy path | 已有测试 |

## Requirements

### MUST
- R1. 为 `stream_generator` 新增测试，覆盖 3 个分支（正常完成 / CancelledError / 异常）
- R2. 为 `IngestService` 新增测试，覆盖 md 解析 happy path
- R3. 测试文件分别放在 `backend/tests/` 下，遵循现有 `test_*.py` 命名
- R4. 所有新测试本地 `pytest` 通过，CI 自动运行

### SHOULD
- R5. `IngestService` 补充 `ingest_pdf` happy path（PDF 解析）
- R6. `IngestService` 补充 `ingest_url` happy path（URL 抓取）
- R7. `IngestService` 补充 `_ingest_questions` 去重路径（content_hash 重复时跳过）

### COULD
- R8. `stream_generator` 测试 partial answer 在 CancelledError 时正确保存到 `conversations` 字典
- R9. `IngestService` 异常分支：ChromaDB 写入失败时的行为

## Acceptance Criteria(可测试)

- [ ] AC1. `pytest tests/test_stream_generator.py` 全绿（至少 3 个用例：正常/CancelledError/异常）
- [ ] AC2. `pytest tests/test_ingest_service.py` 全绿（至少 4 个用例：md/pdf/url happy path + 去重）
- [ ] AC3. 后端总测试数从 98 增加到 ≥108
- [ ] AC4. 后端覆盖率从 52% 提高到 ≥60%（`--cov=app`）
- [ ] AC5. CI 三个 job 全绿（`frontend-tests` / `frontend-build` / `backend-tests`）
- [ ] AC6. 不修改现有测试的核心断言逻辑（只增新文件/新用例，或仅加 fixture）

## Out of Scope

- `path_guard.py` — 已全覆盖
- `evaluator.py` — 已有 245 行测试
- `retriever.py` — 已有测试
- 前端测试
- RAG 参数调优

## Open Questions

- ~~Q1. IngestService mock 方案~~ → ✅ **复用 `test_questions_api.py` 的 `fake_vs` fixture 模式**（`monkeypatch` 替换 `__init__`，设 `self.vector_store` + `self.db`）。_isolate_db 已提供 SQLite 隔离。
- ~~Q2. CancelledError 测试方案~~ → ✅ **mock `rag_service.query_stream` 抛 `CancelledError`**，验证 `conversations` 字典保存了 partial answer。简单直接，不依赖 transport 层。
