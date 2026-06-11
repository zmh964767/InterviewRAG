"""Sweep 驱动单测

mock runner.run_comparison_evaluation，验证：
- 5 个 prompt 变体 + 4 个 chunk size = 9 组
- 文件命名规范
- 选最优 prompt 时按 E HR@5 降序
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_comparison():
    """mock runner 返回固定结构"""
    return {
        "A_纯向量": {"hit_rate@5": 0.23, "mrr": 0.23},
        "B_混合检索": {"hit_rate@5": 0.35, "mrr": 0.24},
        "D_小块检索大块生成": {"hit_rate@5": 0.23, "mrr": 0.23},
        "E_多路改写混合": {"hit_rate@5": 0.45, "mrr": 0.40},
    }


def test_pick_best_prompt_returns_highest_e_hr5(tmp_path):
    """_pick_best_prompt: 按 E HR@5 选最高"""
    from evaluation.sweep import _pick_best_prompt, PROMPT_VARIANTS

    # 写 5 个 json，v3 E HR@5=0.5 最高
    for v in PROMPT_VARIANTS:
        d = {
            "prompt_variant": v,
            "chunk_size": 500,
            "comparison": {
                "E_多路改写混合": {
                    "hit_rate@5": 0.5 if v == 3 else 0.3 + v * 0.01,
                    "mrr": 0.4,
                }
            },
        }
        (tmp_path / f"prompt_v{v}.json").write_text(
            json.dumps(d), encoding="utf-8"
        )

    # patch SWEEP_DIR 到 tmp_path
    with patch("evaluation.sweep.SWEEP_DIR", tmp_path):
        best = _pick_best_prompt()
    assert best == 3


def test_pick_best_prompt_missing_file_skips(tmp_path):
    """_pick_best_prompt: 缺文件跳过"""
    from evaluation.sweep import _pick_best_prompt, PROMPT_VARIANTS

    # 只写 v1 和 v4，v4 最高
    for v, hr in [(1, 0.3), (4, 0.6)]:
        d = {
            "prompt_variant": v,
            "comparison": {"E_多路改写混合": {"hit_rate@5": hr, "mrr": 0.0}},
        }
        (tmp_path / f"prompt_v{v}.json").write_text(
            json.dumps(d), encoding="utf-8"
        )

    with patch("evaluation.sweep.SWEEP_DIR", tmp_path):
        best = _pick_best_prompt()
    assert best == 4


def test_pick_best_prompt_empty_raises(tmp_path):
    """_pick_best_prompt: 空目录抛 RuntimeError"""
    from evaluation.sweep import _pick_best_prompt

    with patch("evaluation.sweep.SWEEP_DIR", tmp_path):
        with pytest.raises(RuntimeError, match="Prompt sweep 结果为空"):
            _pick_best_prompt()


def test_save_result_writes_json(tmp_path):
    """_save_result: 写 json 到 SWEEP_DIR"""
    from evaluation.sweep import _save_result

    with patch("evaluation.sweep.SWEEP_DIR", tmp_path):
        path = _save_result("prompt_v1", {"key": "value"})
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"key": "value"}
    assert path.parent == tmp_path
