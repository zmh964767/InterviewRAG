"""Reingest 单测

mock VectorStore.delete_all + add_documents，验证：
- 临时设置 CHUNK_SIZE 环境变量
- 清空 + 直接写入 ChromaDB（跳过 SQLite）
- 返回统计正确
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_raw_dir(tmp_path):
    """造一个 data/raw/ 目录 + 2 个 md 文件"""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "a.md").write_text(
        "# 题1\n\n## 题目：X\n\n答案：Y\n", encoding="utf-8"
    )
    (raw / "b.md").write_text(
        "# 题2\n\n## 题目：Z\n\n答案：W\n", encoding="utf-8"
    )
    return raw


def test_reingest_clears_and_reimports(fake_raw_dir):
    """reingest: 清空 ChromaDB → 直接 add_documents"""
    from evaluation import reingest

    mock_vs = MagicMock()
    mock_vs.count.return_value = 5

    with patch("evaluation.reingest.VectorStore", return_value=mock_vs), \
         patch("evaluation.reingest.parse_md_content",
               return_value=[MagicMock(id="q1", question="Q", answer="A",
                                       category="", difficulty="", source="")]):
        result = reingest.reingest_with_chunk_size(800, raw_dir=fake_raw_dir)

    mock_vs.delete_all.assert_called_once()
    assert mock_vs.add_documents.call_count >= 1
    assert result == {"chunk_size": 800, "reingested": 2, "files": 2}
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

    call_count = [0]

    def parse_side_effect(content, source):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("parse error")
        return [MagicMock(id="q2", question="Z", answer="W",
                          category="", difficulty="", source="")]

    mock_vs = MagicMock()
    mock_vs.count.return_value = 1

    with patch("evaluation.reingest.VectorStore", return_value=mock_vs), \
         patch("evaluation.reingest.parse_md_content", side_effect=parse_side_effect):
        result = reingest.reingest_with_chunk_size(200, raw_dir=fake_raw_dir)

    # 第一个文件抛异常 → 只处理了第二个文件（1 条）
    assert mock_vs.add_documents.call_count == 1
    assert result["files"] == 1
    assert result["reingested"] == 1


def test_reingest_batch_small_docs(fake_raw_dir):
    """reingest: 单批文档小于 50，不分批"""
    from evaluation import reingest

    mock_vs = MagicMock()
    mock_vs.count.return_value = 1
    with patch("evaluation.reingest.VectorStore", return_value=mock_vs), \
         patch("evaluation.reingest.parse_md_content",
               return_value=[MagicMock(id="q1", question="Q", answer="A",
                                       category="", difficulty="", source="")]):
        result = reingest.reingest_with_chunk_size(500, raw_dir=fake_raw_dir)

    # 2 个文件每文件 1 个 doc = 2 次 add_documents
    assert mock_vs.add_documents.call_count == 2
    call_args_list = mock_vs.add_documents.call_args_list
    for call_args in call_args_list:
        kwargs = call_args[1]
        ids = kwargs.get("ids") or call_args[0][0]
        assert len(ids) == 1  # 每批 1 条
    assert result["reingested"] == 2
