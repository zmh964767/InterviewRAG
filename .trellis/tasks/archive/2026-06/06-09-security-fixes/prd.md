# 修复审查 P0/P1 安全漏洞

## Scope

修复项目审查发现的 3 个 P0 + 1 个 P1 安全问题：

1. [P0] eval 路径遍历 — `ts` 参数校验
2. [P0] CORS 全开 — 限制 origin
3. [P1] `asyncio` 未 import — query.py 补 import
4. [P1] `_last_sources` 竞争 — query_stream 返回 sources

## Acceptance Criteria

- [ ] `eval_detail` 的 `ts` 参数只允许 `\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}` 格式，其他返回 400
- [ ] CORS `allow_origins` 为 `["http://localhost:3000"]`，无 `allow_credentials`
- [ ] `query.py` 顶部有 `import asyncio`
- [ ] `rag_service.query_stream` 返回 `(chunk, sources)` 元组，不存实例属性
- [ ] `npm run build` + `npm test` 通过
