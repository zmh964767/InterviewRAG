# 数据库规范

> InterviewRAG 数据库使用规范（SQLite + ChromaDB）

---

## SQLite（元数据存储）

### 用途

存储面试题元数据（分类、标签、创建时间等），不存储向量。

### ORM

用 Python 标准库 `sqlite3`，不用 SQLAlchemy（MVP 够轻量）。

### 命名规范

- 表名：snake_case 复数（`questions`、`sessions`）
- 列名：snake_case（`created_at`、`question_text`）
- 主键：`id`（INTEGER 自增）
- 外键：`{表名}_id`（`category_id`）

### 规则

- 所有写操作用事务（`BEGIN` / `COMMIT`）
- 查询必须参数化，禁止字符串拼接（防 SQL 注入）
- 数据库文件放在 `data/` 目录

---

## ChromaDB（向量存储）

### 用途

存储面试题的向量表示，支持语义搜索。

### 规则

- 持久化目录：`data/chroma/`
- Collection 命名：`interview_questions`
- 元数据字段：`question_id`、`category`、`difficulty`
- 每次导入后验证文档数量

### 查询模式

```python
results = collection.query(
    query_texts=["用户问题"],
    n_results=5,
    include=["documents", "metadatas", "distances"]
)
```

---

## 常见错误

- ❌ 忘记关闭 SQLite 连接（用 `with` 语句）
- ❌ ChromaDB 查询不加 `include` 参数
- ❌ SQLite 和 ChromaDB 数据不同步
