"""Sweep 结果汇总单测

mock 9 个 json，验证：
- sweep_summary.csv 9 行
- WINNER.md 选了 E HR@5 最高的组合
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def sweep_9_files(tmp_path):
    """造 5 个 prompt_v*.json + 4 个 chunk_*.json"""
    # 5 个 prompt 变体（v3 最高 0.55）
    for v, hr in [(1, 0.40), (2, 0.48), (3, 0.55), (4, 0.45), (5, 0.42)]:
        d = {
            "prompt_variant": v,
            "chunk_size": 500,
            "timestamp": f"2026-06-11T10:0{v}:00",
            "duration_s": 60.0,
            "comparison": {
                "A_纯向量": {"hit_rate@5": 0.23, "mrr": 0.23},
                "B_混合检索": {"hit_rate@5": 0.35, "mrr": 0.24},
                "E_多路改写混合": {"hit_rate@5": hr, "mrr": hr * 0.9},
            },
        }
        (tmp_path / f"prompt_v{v}.json").write_text(
            json.dumps(d), encoding="utf-8"
        )
    # 4 个 chunk size（prompt_variant=3, size=800 最高 0.6）
    for size, hr in [(200, 0.50), (500, 0.55), (800, 0.60), (1200, 0.52)]:
        d = {
            "prompt_variant": 3,
            "chunk_size": size,
            "timestamp": f"2026-06-11T11:{size // 100}:00",
            "duration_s": 80.0,
            "comparison": {
                "A_纯向量": {"hit_rate@5": 0.23, "mrr": 0.23},
                "B_混合检索": {"hit_rate@5": 0.35, "mrr": 0.24},
                "E_多路改写混合": {"hit_rate@5": hr, "mrr": hr * 0.9},
            },
        }
        (tmp_path / f"chunk_{size}.json").write_text(
            json.dumps(d), encoding="utf-8"
        )
    return tmp_path


def test_generate_summary_csv_writes_9_rows(sweep_9_files):
    """generate_summary_csv: 9 行 + 正确表头"""
    from evaluation.sweep_results import generate_summary_csv

    out = generate_summary_csv(sweep_9_files)
    assert out.exists()

    text = out.read_text(encoding="utf-8")
    lines = text.strip().split("\n")
    assert len(lines) == 10  # 1 表头 + 9 行
    assert "type" in lines[0]
    assert "E_hr5" in lines[0]


def test_generate_winner_md_picks_highest_e_hr5(sweep_9_files):
    """generate_winner_md: 选 E HR@5 最高 (chunk_800, 0.60)"""
    from evaluation.sweep_results import generate_winner_md

    out = generate_winner_md(sweep_9_files, baseline_e_hr5=0.3529)
    text = out.read_text(encoding="utf-8")

    # 总冠军应该是 chunk_800 (E_hr5=0.60)
    assert "**E HR@5**" in text
    assert "0.6000" in text
    assert "chunk" in text
    # 包含"落地建议"段
    assert "落地建议" in text
    # 包含顺序假设说明
    assert "单变量顺序" in text or "顺序假设" in text


def test_generate_winner_md_handles_empty_dir(tmp_path):
    """generate_winner_md: 空目录不崩"""
    from evaluation.sweep_results import generate_winner_md

    out = generate_winner_md(tmp_path)
    assert out.exists()
    assert "无 sweep 结果" in out.read_text(encoding="utf-8")


def test_build_rows_returns_correct_count(sweep_9_files):
    """_build_rows: 9 行"""
    from evaluation.sweep_results import _build_rows

    rows = _build_rows(sweep_9_files)
    assert len(rows) == 9
    types = {r["type"] for r in rows}
    assert types == {"prompt", "chunk"}


def test_find_winner_returns_max_e_hr5(sweep_9_files):
    """_find_winner: 选 E_hr5 最大行"""
    from evaluation.sweep_results import _build_rows, _find_winner

    rows = _build_rows(sweep_9_files)
    winner = _find_winner(rows)
    assert winner["E_hr5"] == 0.60
    assert winner["chunk_size"] == 800
    assert winner["type"] == "chunk"
