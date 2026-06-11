"""按指定 chunk_size 重建 ChromaDB 索引

sweep 调优时，chunk_size 变化需要重新导入数据。
注意：直接写 ChromaDB（绕过 SQLite dedup），因为 sweep 只评估检索效果。
"""

import logging
import os
from pathlib import Path

from app.config import get_settings
from app.core.vectorstore import VectorStore
from app.parsers.md_parser import parse_md_content

logger = logging.getLogger(__name__)


def reingest_with_chunk_size(
    chunk_size: int,
    raw_dir: Path | None = None,
) -> dict:
    """按指定 chunk_size 重建 ChromaDB 索引。

    注意：直接解析 raw/.md 文件后走 VectorStore.add_documents 导入，
    不经过 IngestService（跳过 SQLite 去重检查）。

    Args:
        chunk_size: 新的 chunk 大小（覆盖 Settings.chunk_size）
        raw_dir: 原始 .md 文件目录，默认 ./data/raw

    Returns:
        {"chunk_size": int, "reingested": int, "files": int}
    """
    # 1. 覆盖 env，清 lru_cache 让 Settings 读到新值
    os.environ["CHUNK_SIZE"] = str(chunk_size)
    get_settings.cache_clear()

    # 2. 清空 ChromaDB（不动 SQLite）
    vs = VectorStore()
    vs.delete_all()
    logger.info(f"reingest: ChromaDB 已清空, count={vs.count()}")

    # 3. 从 data/raw 重新解析
    raw_dir = raw_dir or Path("./data/raw")
    if not raw_dir.exists():
        logger.warning(f"raw 目录不存在: {raw_dir}")
        return {"chunk_size": chunk_size, "reingested": 0, "files": 0}

    total_added = 0
    file_count = 0
    for md_file in sorted(raw_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            questions = parse_md_content(content, source=md_file.name)
            # 直接走 VectorStore.add_documents（绕过 SQLite）
            documents = []
            metadatas = []
            ids = []
            for q in questions:
                ids.append(q.id)
                documents.append(f"题目：{q.question}\n\n答案：{q.answer}")
                metadatas.append({
                    "question_id": q.id,
                    "category": q.category or "",
                    "difficulty": q.difficulty or "",
                    "source": q.source or "",
                })
            if documents:
                BATCH_SIZE = 50
                for i in range(0, len(documents), BATCH_SIZE):
                    vs.add_documents(
                        ids=ids[i:i + BATCH_SIZE],
                        documents=documents[i:i + BATCH_SIZE],
                        metadatas=metadatas[i:i + BATCH_SIZE],
                    )
                total_added += len(documents)
            file_count += 1
            logger.info(
                f"reingest: {md_file.name} -> {len(documents)} 条 (直接 ChromaDB)"
            )
        except Exception as e:
            logger.error(f"reingest: 解析 {md_file.name} 失败: {e}")

    final_count = vs.count()
    logger.info(
        f"reingest 完成: chunk_size={chunk_size}, "
        f"files={file_count}, added={total_added}, "
        f"vectorstore_count={final_count}"
    )
    return {
        "chunk_size": chunk_size,
        "reingested": total_added,
        "files": file_count,
    }
