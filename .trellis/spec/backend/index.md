# 后端开发规范

> InterviewRAG 后端开发最佳实践（FastAPI + ChromaDB + 智谱 API）

---

## 技术栈

- **框架**：FastAPI (Python 3.11+)
- **向量数据库**：ChromaDB（文件存储）
- **元数据数据库**：SQLite
- **LLM**：智谱 GLM-4-Flash
- **Embedding**：智谱 embedding-3

---

## 规范索引

| 规范 | 描述 | 状态 |
|------|------|------|
| [目录结构](./directory-structure.md) | 模块组织和文件布局 | ✅ 已完成 |
| [数据库规范](./database-guidelines.md) | SQLite + ChromaDB 使用规范 | ✅ 已完成 |
| [错误处理](./error-handling.md) | 异常类型、处理策略 | ✅ 已完成 |
| [质量规范](./quality-guidelines.md) | 代码标准、禁止模式 | ✅ 已完成 |
| [日志规范](./logging-guidelines.md) | 结构化日志、日志级别 | ✅ 已完成 |

---

## 开发前检查清单

- [ ] 确认 Python 版本 >= 3.11
- [ ] 确认已安装依赖：`pip install -r requirements.txt`
- [ ] 确认环境变量已配置（`.env` 文件）
  - `ZHIPU_API_KEY`：智谱 API 密钥
  - `CHROMA_PERSIST_DIR`：ChromaDB 持久化目录
  - `SQLITE_DB_PATH`：SQLite 数据库路径
- [ ] 确认 ChromaDB 目录可写

---

## 质量检查

- [ ] 所有函数有类型标注
- [ ] 所有异常用自定义异常类
- [ ] 外部调用有超时处理
- [ ] 无硬编码密钥
- [ ] 日志级别正确
- [ ] 核心服务有测试
