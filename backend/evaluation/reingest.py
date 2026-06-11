"""按指定 chunk_size 重建 ChromaDB 索引

sweep 调优时，chunk_size 变化需要重新导入数据。本模块：
1. 临时覆盖 os.environ["CHUNK_SIZE"]（Settings 读 env）
2. 清空 ChromaDB
3. 从 data/raw/ 重新解析所有 .md 文件并导入
4. 返回导入统计
"""

import logging
import os
from pathlib import Path

from app.core.vectorstore import VectorStore
from app.parsers.md_parser import parse_md_content
from app.services.ingest_service import IngestService

logger = logging.getLogger(__name__)


def reingest_with_chunk_size(
    chunk_size: int,
    raw_dir: Path | None = None,
) -> dict:
    """按指定 chunk_size 重建 ChromaDB 索引。

    Args:
        chunk_size: 新的 chunk 大小（覆盖 Settings.chunk_size）
        raw_dir: 原始 .md 文件目录，默认 ./data/raw

    Returns:
        {"chunk_size": int, "reingested": int, "files": int}
    """
    # 1. 覆盖 env，让 Settings 读到新值
    os.environ["CHUNK_SIZE"] = str(chunk_size)

    # 2. 清空 ChromaDB（不动 SQLite，question_id 仍然唯一）
    vs = VectorStore()
    vs.delete_all()

    # 3. 从 data/raw 重新解析 + 导入
    raw_dir = raw_dir or Path("./data/raw")
    if not raw_dir.exists():
        logger.warning(f"raw 目录不存在: {raw_dir}")
        return {"chunk_size": chunk_size, "reingested": 0, "files": 0}

    ingest = IngestService()
    total_ingested = 0
    file_count = 0
    for md_file in sorted(raw_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            questions = parse_md_content(content, source=md_file.name)
            result = ingest._ingest_questions(questions)
            total_ingested += result.get("ingested", 0)
            file_count += 1
            logger.info(
                f"reingest: {md_file.name} -> {result.get('ingested', 0)} 条"
            )
        except Exception as e:
            logger.error(f"reingest: 解析 {md_file.name} 失败: {e}")

    return {
        "chunk_size": chunk_size,
        "reingested": total_ingested,
        "files": file_count,
    }
