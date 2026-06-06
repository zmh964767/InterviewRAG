"""SQLite 数据库管理"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class Database:
    """SQLite 数据库"""

    def __init__(self):
        settings = get_settings()
        db_path = Path(settings.sqlite_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """初始化表结构"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT DEFAULT '中等',
                source TEXT,
                tags TEXT DEFAULT '[]',
                content_hash TEXT UNIQUE,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self.conn.commit()
        logger.info("SQLite 数据库已初始化")

    def insert_question(self, question_data: dict) -> bool:
        """插入题目，返回是否成功（重复则跳过）"""
        content = f"{question_data['question']}|{question_data['answer']}"
        content_hash = hashlib.md5(content.encode()).hexdigest()

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO questions (id, question, answer, category, difficulty, source, tags, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_data["id"],
                    question_data["question"],
                    question_data["answer"],
                    question_data["category"],
                    question_data.get("difficulty", "中等"),
                    question_data.get("source", ""),
                    json.dumps(question_data.get("tags", []), ensure_ascii=False),
                    content_hash,
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # 重复内容，跳过
            return False

    def get_all_questions(self) -> list[dict]:
        """获取所有题目"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM questions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_question_by_id(self, question_id: str) -> dict | None:
        """根据 ID 获取题目"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        """返回题目数量"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions")
        return cursor.fetchone()[0]

    def close(self):
        """关闭连接"""
        self.conn.close()
