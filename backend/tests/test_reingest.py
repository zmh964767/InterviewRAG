"""Reingest 单测

mock VectorStore.delete_all + IngestService._ingest_questions，验证：
- 临时设置 CHUNK_SIZE 环境变量
- 清空 + 重建流程
- 返回统计正确
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def fake_raw_dir(tmp_path):
    """造一个 data/raw/ 目录 + 2 个 md 文件"""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "a.md").write_text("# 题1\n\n## 题目：X\n\n答案：Y\n", encoding="utf-8")
    (raw / "b.md").write_text("# 题2\n\n## 题目：Z\n\n答案：W\n", encoding="utf-8")
    return raw


def test_reingest_clears_and_reimports(fake_raw_dir):
    """reingest: 清空 ChromaDB + 解析 + 导入"""
    from evaluation import reingest

    mock_vs = MagicMock()
    mock_ingest = MagicMock()
    mock_ingest._ingest_questions.side_effect = [
        {"ingested": 1, "duplicates": 0, "errors": 0},
        {"ingested": 2, "duplicates": 0, "errors": 0},
    ]

    with patch("evaluation.reingest.VectorStore", return_value=mock_vs), \
         patch("evaluation.reingest.IngestService", return_value=mock_ingest), \
         patch("evaluation.reingest.parse_md_content",
               side_effect=lambda c, source: [f"Q({source})"] * 1):
        result = reingest.reingest_with_chunk_size(800, raw_dir=fake_raw_dir)

    # 验证
    mock_vs.delete_all.assert_called_once()
    assert mock_ingest._ingest_questions.call_count == 2
    assert result == {"chunk_size": 800, "reingested": 3, "files": 2}
    # 验证 os.environ 被覆盖
    assert os.environ["CHUNK_SIZE"] == "800"


def test_reingest_raw_dir_missing_returns_zero(tmp_path):
    """reingest: raw 目录不存在 → 返回 0"""
    from evaluation import reingest

    fake_raw = tmp_path / "nonexistent"
    mock_vs = MagicMock()
    with patch("evaluation.reingest.VectorStore", return_value=mock_vs):
        result = reingest.reingest_with_chunk_size(500, raw_dir=fake_raw)

    mock_vs.delete_all.assert_called_once()
    assert result == {"chunk_size": 500, "reingested": 0, "files": 0}


def test_reingest_parse_error_continues(fake_raw_dir):
    """reingest: 单个文件解析失败 → 继续处理其他文件"""
    from evaluation import reingest

    mock_vs = MagicMock()
    mock_ingest = MagicMock()
    # 第一个文件解析失败（抛异常），第二个文件成功但 ingest 返回 0
    mock_ingest._ingest_questions.return_value = {
        "ingested": 0, "duplicates": 0, "errors": 1
    }

    call_count = [0]
    def parse_side_effect(c, source):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("parse error")
        return ["Q1"]

    with patch("evaluation.reingest.VectorStore", return_value=mock_vs), \
         patch("evaluation.reingest.IngestService", return_value=mock_ingest), \
         patch("evaluation.reingest.parse_md_content", side_effect=parse_side_effect):
        result = reingest.reingest_with_chunk_size(200, raw_dir=fake_raw_dir)

    # 第一个文件抛异常 → 不调 _ingest_questions → _ingest_questions 只被调 1 次（第二个文件）
    assert mock_ingest._ingest_questions.call_count == 1
    assert result["files"] == 1
    assert result["reingested"] == 0
