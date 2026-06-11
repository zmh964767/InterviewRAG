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

        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
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

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """将 SQLite Row 转为 dict，tags 字段从 JSON 字符串解析为 list"""
        d = dict(row)
        tags = d.get("tags")
        if isinstance(tags, str):
            try:
                d["tags"] = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                d["tags"] = []
        return d

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
        return [self._row_to_dict(row) for row in rows]

    def get_question_by_id(self, question_id: str) -> dict | None:
        """根据 ID 获取题目"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def delete_by_id(self, question_id: str) -> bool:
        """根据 ID 删除题目

        Returns:
            True 表示成功删除，False 表示题目不存在
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def list_questions(
        self,
        filters: dict,
        page: int,
        size: int,
    ) -> tuple[list[dict], int]:
        """分页查询题目

        Args:
            filters: {q, category, difficulty}
            page: 1-based
            size: 页大小

        Returns:
            (items, total)
        """
        where_clauses: list[str] = []
        params: list = []

        q = (filters.get("q") or "").strip()
        if q:
            where_clauses.append("(question LIKE ? OR answer LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])

        category = (filters.get("category") or "").strip()
        if category:
            where_clauses.append("category = ?")
            params.append(category)

        difficulty = (filters.get("difficulty") or "").strip()
        if difficulty:
            where_clauses.append("difficulty = ?")
            params.append(difficulty)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cursor = self.conn.cursor()

        # 总量
        cursor.execute(f"SELECT COUNT(*) FROM questions {where_sql}", params)
        total = cursor.fetchone()[0]

        # 分页
        offset = (page - 1) * size
        cursor.execute(
            f"SELECT * FROM questions {where_sql} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, size, offset),
        )
        items = [self._row_to_dict(row) for row in cursor.fetchall()]
        return items, total

    def list_categories(self) -> list[str]:
        """返回所有非空分类（去重，按字母序）"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT DISTINCT category FROM questions "
            "WHERE category IS NOT NULL AND category != '' "
            "ORDER BY category"
        )
        return [row[0] for row in cursor.fetchall()]

    def count(self) -> int:
        """返回题目数量"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions")
        return cursor.fetchone()[0]

    def count_by_category(self) -> dict[str, int]:
        """按分类聚合计数（SQL 层面，不拉全量数据）"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COALESCE(NULLIF(category, ''), '未分类'), COUNT(*) "
            "FROM questions GROUP BY COALESCE(NULLIF(category, ''), '未分类')"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def close(self):
        """关闭连接"""
        self.conn.close()
