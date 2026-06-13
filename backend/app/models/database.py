"""SQLite 数据库管理"""

import hashlib
import json
import logging
import sqlite3
import uuid
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL UNIQUE,
                conversation_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                message_content TEXT NOT NULL,
                message_role TEXT NOT NULL,
                client_ip TEXT,
                user_agent TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating)")
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

    def batch_delete(self, ids: list[str]) -> int:
        """批量删除题目，返回实际删除条数

        Args:
            ids: 要删除的题目 ID 列表

        Returns:
            实际删除的条数（不存在的 ID 不影响结果）
        """
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        cursor = self.conn.cursor()
        cursor.execute(
            f"DELETE FROM questions WHERE id IN ({placeholders})",
            ids,
        )
        self.conn.commit()
        return cursor.rowcount

    def update_question(self, question_id: str, fields: dict) -> bool:
        """更新题目字段，返回是否成功"""
        import sqlite3 as _sqlite3
        allowed = {"question", "answer", "category", "difficulty"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False

        # 如果改了 question 或 answer，重算 content_hash
        if "question" in updates or "answer" in updates:
            q = self.get_question_by_id(question_id)
            if not q:
                return False
            new_q = updates.get("question", q["question"])
            new_a = updates.get("answer", q["answer"])
            updates["content_hash"] = hashlib.md5(
                f"{new_q}|{new_a}".encode()
            ).hexdigest()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [question_id]
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"UPDATE questions SET {set_clause} WHERE id = ?", values)
            self.conn.commit()
            return cursor.rowcount > 0
        except _sqlite3.IntegrityError:
            return False

    def close(self):
        """关闭连接"""
        self.conn.close()

    # =========================================================================
    # 用户反馈
    # =========================================================================

    def insert_feedback(self, data: dict) -> str:
        """插入/覆盖反馈(利用 message_id UNIQUE 约束 + INSERT OR REPLACE),返回 feedback.id"""
        feedback_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO feedback (
                id, message_id, conversation_id, rating, comment,
                message_content, message_role, client_ip, user_agent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                data["message_id"],
                data["conversation_id"],
                data["rating"],
                data.get("comment"),
                data["message_content"],
                data["message_role"],
                data.get("client_ip"),
                data.get("user_agent"),
            ),
        )
        self.conn.commit()

        # INSERT OR REPLACE 会按 message_id 覆盖;查回当前最新 id(可能是之前传进去的旧 id)
        cursor.execute(
            "SELECT id FROM feedback WHERE message_id = ?",
            (data["message_id"],),
        )
        row = cursor.fetchone()
        return row["id"] if row else feedback_id

    def get_feedback(
        self,
        rating: int | None = None,
        since: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> dict:
        """分页查询反馈列表"""
        where_clauses: list[str] = []
        params: list = []

        if rating is not None:
            where_clauses.append("rating = ?")
            params.append(rating)
        if since:
            where_clauses.append("created_at >= ?")
            params.append(since)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cursor = self.conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM feedback {where_sql}", params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * size
        cursor.execute(
            f"SELECT * FROM feedback {where_sql} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, size, offset),
        )
        items = [self._row_to_dict(row) for row in cursor.fetchall()]

        return {"items": items, "total": total, "page": page, "size": size}

    def get_feedback_stats(self, since: str | None = None) -> dict:
        """按 rating 聚合统计(差评率 = negative / total)"""
        cursor = self.conn.cursor()
        if since:
            cursor.execute(
                "SELECT rating, COUNT(*) FROM feedback WHERE created_at >= ? GROUP BY rating",
                (since,),
            )
        else:
            cursor.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating")

        positive = 0
        negative = 0
        for row in cursor.fetchall():
            if row["rating"] == 1:
                positive = row["COUNT(*)"]
            elif row["rating"] == -1:
                negative = row["COUNT(*)"]

        total = positive + negative
        rate = (negative / total) if total > 0 else 0.0
        return {"positive": positive, "negative": negative, "total": total, "rate": rate}

    def get_feedback_by_message_id(self, message_id: str) -> dict | None:
        """根据 message_id 查询反馈(辅助:验证 INSERT OR REPLACE 覆盖)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM feedback WHERE message_id = ?", (message_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None
