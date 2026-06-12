"""测试 /api/admin/eval/sweep 端点

策略:monkeypatch admin_eval.RESULTS_DIR 到 tmp_path,预先写入几个 sweep json。
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def admin_token(client):
    res = client.post("/api/auth/login", json={"password": "admin123"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _write_sweep(path: Path, type_: str, variant_or_size, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.fixture
def fake_results_dir(tmp_path, monkeypatch):
    """覆盖 admin_eval.RESULTS_DIR,写入 9 个 sweep json"""
    from app.api import admin_eval

    fake_dir = tmp_path / "results"
    fake_dir.mkdir()
    sweep_dir = fake_dir / "sweep"
    sweep_dir.mkdir()

    # 5 个 prompt 变体扫描
    for v in range(1, 6):
        _write_sweep(
            sweep_dir / f"prompt_v{v}.json",
            "prompt",
            v,
            {
                "prompt_variant": v,
                "chunk_size": 500,
                "duration_s": 60.0 + v,
                "comparison": {
                    "E_多路改写混合": {
                        "hit_rate@5": 0.30 + v * 0.01,  # 0.31, 0.32, 0.33, 0.34, 0.35
                        "mrr": 0.20 + v * 0.01,
                    },
                    "B_混合检索": {
                        "hit_rate@5": 0.30,
                        "mrr": 0.22,
                    },
                },
            },
        )

    # 4 个 chunk size 扫描
    for size in (200, 500, 800, 1200):
        _write_sweep(
            sweep_dir / f"chunk_{size}.json",
            "chunk",
            size,
            {
                "prompt_variant": 1,
                "chunk_size": size,
                "duration_s": 50.0 + size / 10,
                "comparison": {
                    "E_多路改写混合": {
                        # chunk_800 给 0.40,作为 winner
                        "hit_rate@5": 0.35 + (0.05 if size == 800 else 0.00),
                        "mrr": 0.25,
                    },
                    "B_混合检索": {
                        "hit_rate@5": 0.30,
                        "mrr": 0.22,
                    },
                },
            },
        )

    monkeypatch.setattr(admin_eval, "RESULTS_DIR", fake_dir)
    return fake_dir


class TestEvalSweepEndpoint:
    def test_sweep_returns_9_rows(self, client, admin_headers, fake_results_dir):
        """正常情况下返回 9 行(5 prompt + 4 chunk)"""
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.status_code == 200, res.text
        data = res.json()

        assert len(data["rows"]) == 9
        # 5 个 type=prompt
        assert sum(1 for r in data["rows"] if r["type"] == "prompt") == 5
        # 4 个 type=chunk
        assert sum(1 for r in data["rows"] if r["type"] == "chunk") == 4

    def test_sweep_winner_is_max_e_hr5(self, client, admin_headers, fake_results_dir):
        """winner 是 E_hr5 最高的组合 → chunk_800 (0.40)"""
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        data = res.json()
        assert data["winner"] is not None
        assert data["winner"]["type"] == "chunk"
        assert data["winner"]["chunk_size"] == 800
        assert data["winner"]["E_hr5"] == pytest.approx(0.40, abs=1e-3)

    def test_sweep_only_e_and_b_strategies(self, client, admin_headers, fake_results_dir):
        """只取 E 和 B 策略的字段,响应里不应有 A/D 等"""
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        data = res.json()
        row = data["rows"][0]
        assert "E_hr5" in row
        assert "E_mrr" in row
        assert "B_hr5" in row
        assert "B_mrr" in row
        # 不应出现 A_纯向量 等其他策略的字段
        assert "A_hr5" not in row
        assert "D_hr5" not in row

    def test_sweep_preserves_duration(self, client, admin_headers, fake_results_dir):
        """耗时字段被保留"""
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        data = res.json()
        for row in data["rows"]:
            assert row["duration_s"] is not None
            assert row["duration_s"] > 0

    def test_sweep_empty_dir_returns_empty(self, client, admin_headers, tmp_path, monkeypatch):
        """sweep 目录不存在或为空时返回空 rows + winner=None"""
        from app.api import admin_eval

        empty_dir = tmp_path / "empty_results"
        empty_dir.mkdir()
        monkeypatch.setattr(admin_eval, "RESULTS_DIR", empty_dir)

        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["rows"] == []
        assert data["winner"] is None

    def test_sweep_missing_some_files(self, client, admin_headers, fake_results_dir):
        """部分文件缺失时,只读取存在的,rows 数量减少"""
        from app.api import admin_eval
        # 删掉 2 个 prompt 文件
        (admin_eval.RESULTS_DIR / "sweep" / "prompt_v3.json").unlink()
        (admin_eval.RESULTS_DIR / "sweep" / "prompt_v5.json").unlink()
        # 删掉 1 个 chunk 文件
        (admin_eval.RESULTS_DIR / "sweep" / "chunk_200.json").unlink()

        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        # 3 prompt + 3 chunk = 6 行
        assert len(data["rows"]) == 6
        # winner 仍是 chunk_800
        assert data["winner"]["chunk_size"] == 800

    def test_sweep_requires_auth(self, client, fake_results_dir):
        """无 admin token 返回 401"""
        res = client.get("/api/admin/eval/sweep")
        assert res.status_code in (401, 403)

    # ---- baseline_e_hr5 动态读取 ----

    def test_sweep_baseline_from_latest_summary(self, client, admin_headers, fake_results_dir):
        """写 latest_summary.json,验证 baseline 字段被读取"""
        from app.api import admin_eval

        # context_precision 优先(白名单),期望返回 0.88
        (fake_results_dir / "latest_summary.json").write_text(
            json.dumps({
                "metrics": {
                    "context_precision": 0.88,
                    "faithfulness": 0.50,
                    "answer_relevancy": 0.60,
                    "context_recall": 0.70,
                },
                "total": 17,
                "error_count": 0,
            }),
            encoding="utf-8",
        )

        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["baseline_e_hr5"] == pytest.approx(0.88, abs=1e-6)

    def test_sweep_baseline_zero_when_missing(self, client, admin_headers, fake_results_dir):
        """latest_summary.json 不存在时 baseline=0.0"""
        from app.api import admin_eval

        # 确保 fake_results_dir 下没有 latest_summary.json
        latest_path = fake_results_dir / "latest_summary.json"
        if latest_path.exists():
            latest_path.unlink()

        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["baseline_e_hr5"] == 0.0
        # rows / winner 仍正常返回
        assert len(data["rows"]) == 9
        assert data["winner"] is not None

    def test_sweep_baseline_fallback_chain(self, client, admin_headers, fake_results_dir):
        """字段缺失时按 fallback 链降级"""
        from app.api import admin_eval

        # 1) 只有 faithfulness(无 context_precision) → 取 faithfulness
        (fake_results_dir / "latest_summary.json").write_text(
            json.dumps({
                "metrics": {"faithfulness": 0.42, "answer_relevancy": 0.33},
                "total": 5,
            }),
            encoding="utf-8",
        )
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.json()["baseline_e_hr5"] == pytest.approx(0.42, abs=1e-6)

        # 2) 白名单都缺,只有 answer_relevancy → 取第一个非 0 字段
        (fake_results_dir / "latest_summary.json").write_text(
            json.dumps({"metrics": {"answer_relevancy": 0.55}, "total": 5}),
            encoding="utf-8",
        )
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.json()["baseline_e_hr5"] == pytest.approx(0.55, abs=1e-6)

        # 3) metrics 完全空 / 没有有效值 → 0.0
        (fake_results_dir / "latest_summary.json").write_text(
            json.dumps({"metrics": {}, "total": 0}),
            encoding="utf-8",
        )
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.json()["baseline_e_hr5"] == 0.0

        # 4) JSON 损坏 → 0.0(不抛异常)
        (fake_results_dir / "latest_summary.json").write_text("not-valid-json", encoding="utf-8")
        res = client.get("/api/admin/eval/sweep", headers=admin_headers)
        assert res.json()["baseline_e_hr5"] == 0.0
