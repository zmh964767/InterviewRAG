# 后端目录结构

> InterviewRAG 后端代码组织方式（FastAPI）

---

## 目录布局

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理（环境变量）
│   ├── api/                 # API 路由
│   │   ├── __init__.py
│   │   ├── query.py         # POST /api/query — 问答接口
│   │   ├── ingest.py        # POST /api/ingest — 知识库导入
│   │   └── health.py        # GET /api/health — 健康检查
│   ├── services/            # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── rag_service.py   # RAG 核心流程（检索+生成）
│   │   ├── embed_service.py # 向量化服务
│   │   └── llm_service.py   # LLM 调用封装（智谱 API）
│   ├── models/              # 数据模型
│   │   ├── __init__.py
│   │   ├── schemas.py       # Pydantic 请求/响应模型
│   │   └── database.py      # SQLite 数据库模型
│   ├── core/                # 核心工具
│   │   ├── __init__.py
│   │   ├── vectorstore.py   # ChromaDB 封装
│   │   └── exceptions.py    # 自定义异常类
│   └── utils/               # 通用工具
│       ├── __init__.py
│       └── text_splitter.py # 文本分块工具
├── data/                    # 数据目录
│   ├── questions/           # 原始面试题文件
│   └── chroma/              # ChromaDB 持久化存储
├── tests/                   # 测试文件
│   ├── __init__.py
│   ├── test_query.py
│   ├── test_ingest.py
│   └── test_rag_service.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 命名规范

- **文件名**：snake_case（`rag_service.py`）
- **类名**：PascalCase（`RAGService`）
- **函数名**：snake_case（`query_documents`）
- **常量**：UPPER_SNAKE_CASE（`MAX_CHUNK_SIZE`）

---

## 分层规则

- **api/**：只做参数校验和响应格式化，不放业务逻辑
- **services/**：核心业务逻辑，不直接依赖 FastAPI
- **models/**：数据定义，不放业务逻辑
- **core/**：基础设施封装（向量库、异常）
- **utils/**：纯函数工具，无状态

---

## 禁止事项

- ❌ 在 api/ 层写业务逻辑
- ❌ 在 services/ 层直接 import FastAPI 依赖
- ❌ 硬编码配置（用 config.py 管理环境变量）
- ❌ 循环导入
