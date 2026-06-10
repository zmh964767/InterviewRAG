"""IngestService 单元测试

覆盖：
- ingest_md_content: MD 解析 happy path → SQLite 写入 + ChromaDB 写入
- ingest_pdf_content: PDF 解析 happy path
- ingest_url: URL 抓取 happy path
- _ingest_questions 去重: 重复 content_hash → duplicates 计数
"""

import pytest
from unittest.mock import MagicMock, patch

from app.api import ingest as ingest_mod
from app.models.schemas import Question
import app.core.db as db_module


# ---- fixtures ----


class _FakeVectorStore:
    """最小化 VectorStore mock"""
    def __init__(self):
        self.added: dict = {}

    def add_documents(self, ids, documents, metadatas, embeddings=None):
        self.added["ids"] = ids
        self.added["docs"] = documents
        self.added["metas"] = metadatas


@pytest.fixture(autouse=True)
def _setup_ingest_service(monkeypatch):
    """为每个测试注入假 VectorStore + 重置 IngestService 单例"""
    fake_vs = _FakeVectorStore()
    original_init = IngestService.__init__
    original_ingest = ingest_mod._ingest_service

    def _patched_init(self):
        self.vector_store = fake_vs
        self.db = db_module._db  # 用 _isolate_db 提供的隔离 db

    monkeypatch.setattr(
        "app.services.ingest_service.IngestService.__init__",
        _patched_init,
    )
    ingest_mod._ingest_service = None
    yield fake_vs
    ingest_mod._ingest_service = original_ingest


from app.services.ingest_service import IngestService


def _make_question(id="q1", question="什么是RAG", answer="RAG是检索增强生成", category="LLM"):
    return Question(
        id=id,
        question=question,
        answer=answer,
        category=category,
        difficulty="中等",
        source="test",
    )


# ---- tests ----


class TestIngestMdContent:
    """ingest_md_content happy path"""

    @pytest.mark.asyncio
    async def test_inserts_questions(self):
        """导入 MD 内容应将题目写入 SQLite + ChromaDB"""
        md_content = "# Q1\n\n## 什么是RAG\n\nRAG是检索增强生成的缩写。"

        service = IngestService()
        with patch("app.services.ingest_service.parse_md_content") as mock_parse:
            mock_parse.return_value = [_make_question()]
            result = await service.ingest_md_content(md_content, filename="test.md")

        assert result["ingested"] >= 1
        assert result["errors"] == 0
        # ChromaDB 被调用
        assert len(service.vector_store.added["ids"]) >= 1


class TestIngestPdfContent:
    """ingest_pdf_content happy path"""

    @pytest.mark.asyncio
    async def test_inserts_from_pdf(self):
        """导入 PDF 内容应解析并写入"""
        pdf_bytes = b"%PDF-1.4 fake content"

        service = IngestService()
        with patch("app.services.ingest_service.parse_pdf_content") as mock_parse:
            mock_parse.return_value = [_make_question(id="pdf1")]
            result = await service.ingest_pdf_content(pdf_bytes, filename="doc.pdf")

        assert result["ingested"] == 1
        assert result["errors"] == 0


class TestIngestUrl:
    """ingest_url happy path"""

    @pytest.mark.asyncio
    async def test_inserts_from_url(self):
        """从 URL 抓取并导入"""
        url = "https://example.com/questions"

        service = IngestService()
        with patch("app.services.ingest_service.scrape_url") as mock_scrape:
            mock_scrape.return_value = [_make_question(id="url1"), _make_question(id="url2", question="Q2")]
            result = await service.ingest_url(url)

        assert result["ingested"] == 2
        assert result["errors"] == 0
        # ChromaDB 分批写入（两个文档）
        assert len(service.vector_store.added["ids"]) == 2


class TestIngestDedup:
    """_ingest_questions 去重路径"""

    @pytest.mark.asyncio
    async def test_duplicate_returns_duplicates_count(self):
        """重复导入相同题目，第二次应计为 duplicate"""
        questions = [_make_question()]

        service = IngestService()
        with patch("app.services.ingest_service.parse_md_content") as mock_parse:
            mock_parse.return_value = questions
            result1 = await service.ingest_md_content("content", "a.md")
            # 第二次导入同样的 content → SQLite content_hash 冲突
            result2 = await service.ingest_md_content("content", "a.md")

        assert result1["ingested"] == 1
        assert result1["duplicates"] == 0
        # 第二次同一 question → SQLite 跳过（content_hash 相同）
        # 但 ChromaDB 仍然写入（因为 SQLite 跳过不影响 ChromaDB 的 ids 列表）
        assert result2["duplicates"] == 1


class TestIngestJsonNotFound:
    """ingest_json 文件不存在路径"""

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """文件不存在时返回 errors=1"""
        service = IngestService()
        result = await service.ingest_json("/nonexistent/path.json")
        assert result == {"ingested": 0, "duplicates": 0, "errors": 1}


class TestIngestPdfInvalidPath:
    """ingest_pdf 非法路径"""

    @pytest.mark.asyncio
    async def test_invalid_path_raises(self):
        """非法路径应抛 ValidationError"""
        from app.core.exceptions import ValidationError
        service = IngestService()
        with pytest.raises(ValidationError, match="路径不安全"):
            await service.ingest_pdf("/etc/passwd")
