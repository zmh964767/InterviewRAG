"""数据导入服务

负责将各种来源的面试题导入到 ChromaDB 和 SQLite。
"""

import json
import logging
from pathlib import Path

from app.config import get_settings
from app.core.db import get_db
from app.core.exceptions import ValidationError
from app.core.path_guard import validate_safe_path
from app.core.vectorstore import VectorStore
from app.models.schemas import Question
from app.parsers.md_parser import parse_md_file, parse_md_content
from app.parsers.pdf_parser import parse_pdf, parse_pdf_content
from app.parsers.web_scraper import scrape_url

logger = logging.getLogger(__name__)


class IngestService:
    """数据导入服务"""

    def __init__(self, vector_store: VectorStore | None = None):
        self.vector_store = vector_store or VectorStore()
        self.db = get_db()
        self.settings = get_settings()

    async def ingest_md(self, file_path: str) -> dict:
        """导入 MD 文件（服务端路径，必须在 data/ 白名单内）"""
        try:
            safe_path = validate_safe_path(file_path)
        except Exception as e:
            raise ValidationError(f"路径不安全: {e}")
        questions = parse_md_file(str(safe_path))
        return self._ingest_questions(questions)

    async def ingest_md_content(self, content: str, filename: str) -> dict:
        """导入 MD 内容（前端上传，已经过 Multipart 边界校验）"""
        questions = parse_md_content(content, source=filename)
        return self._ingest_questions(questions)

    async def ingest_pdf(self, file_path: str) -> dict:
        """导入 PDF 文件（服务端路径，必须在 data/ 白名单内）"""
        try:
            safe_path = validate_safe_path(file_path)
        except Exception as e:
            raise ValidationError(f"路径不安全: {e}")
        questions = parse_pdf(str(safe_path))
        return self._ingest_questions(questions)

    async def ingest_pdf_content(self, content: bytes, filename: str) -> dict:
        """导入 PDF 内容（前端上传）"""
        questions = parse_pdf_content(content, filename)
        return self._ingest_questions(questions)

    async def ingest_url(self, url: str) -> dict:
        """从 URL 导入"""
        questions = await scrape_url(url)
        return self._ingest_questions(questions)

    async def ingest_json(self, file_path: str) -> dict:
        """导入 JSON 文件"""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"文件不存在: {file_path}")
            return {"ingested": 0, "duplicates": 0, "errors": 1}

        data = json.loads(path.read_text(encoding="utf-8"))
        questions = [Question(**item) for item in data]
        return self._ingest_questions(questions)

    def _ingest_questions(self, questions: list[Question]) -> dict:
        """将题目导入到 SQLite 和 ChromaDB"""
        ingested = 0
        duplicates = 0
        errors = 0

        ids = []
        documents = []
        metadatas = []

        for q in questions:
            try:
                # 先存 SQLite（去重在 SQLite 层）
                success = self.db.insert_question(q.model_dump(mode="json"))
                if success:
                    ingested += 1
                    # 准备 ChromaDB 数据
                    ids.append(q.id)
                    # ChromaDB 存储题目+答案的组合文本
                    doc_text = f"题目：{q.question}\n\n答案：{q.answer}"
                    documents.append(doc_text)
                    metadatas.append({
                        "question_id": q.id,
                        "category": q.category,
                        "difficulty": q.difficulty,
                        "source": q.source,
                    })
                else:
                    duplicates += 1
            except Exception as e:
                logger.error(f"导入题目失败: {e}")
                errors += 1

        # 分批写入 ChromaDB（智谱 Embedding API 限制单次最多 64 条）
        BATCH_SIZE = 50
        if ids:
            try:
                for i in range(0, len(ids), BATCH_SIZE):
                    batch_ids = ids[i:i + BATCH_SIZE]
                    batch_docs = documents[i:i + BATCH_SIZE]
                    batch_metas = metadatas[i:i + BATCH_SIZE]
                    self.vector_store.add_documents(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_metas,
                    )
                    logger.info(f"ChromaDB 批次 {i // BATCH_SIZE + 1}: 已添加 {len(batch_ids)} 个文档")
                logger.info(f"ChromaDB 总计已添加 {len(ids)} 个文档")
            except Exception as e:
                logger.error(f"ChromaDB 写入失败: {e}")
                errors += len(ids)

        result = {"ingested": ingested, "duplicates": duplicates, "errors": errors}
        logger.info(f"导入完成: {result}")
        return result
