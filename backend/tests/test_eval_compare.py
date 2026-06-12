"""测试 /api/admin/eval/compare 端点

策略:monkeypatch admin_eval.RESULTS_DIR 到 tmp_path,预先写入两个快照 json。
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


def _write_snapshot(path: Path, ts: str, metrics: dict, total: int = 5) -> None:
    path.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "aggregated": metrics,
                "errors": [],
                "total": total,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@pytest.fixture
def fake_results_dir(tmp_path, monkeypatch):
    """覆盖 admin_eval.RESULTS_DIR 指向临时目录"""
    from app.api import admin_eval

    fake_dir = tmp_path / "results"
    fake_dir.mkdir()
    history_dir = fake_dir / "history"
    history_dir.mkdir()

    # latest.json
    _write_snapshot(
        fake_dir / "latest.json",
        "2026-06-12T22-41-09",
        {
            "faithfulness": 0.90,
            "answer_relevancy": 0.80,
            "context_precision": 0.70,
            "context_recall": 0.60,
        },
    )

    # 历史快照:metrics 略低
    _write_snapshot(
        history_dir / "2026-06-08T23-26-02.json",
        "2026-06-08T23-26-02",
        {
            "faithfulness": 0.85,
            "answer_relevancy": 0.85,
            "context_precision": 0.72,
            "context_recall": 0.50,
        },
    )
    # 第二个历史快照
    _write_snapshot(
        history_dir / "2026-06-10T10-00-00.json",
        "2026-06-10T10-00-00",
        {
            "faithfulness": 0.88,
            "answer_relevancy": 0.78,
            "context_precision": 0.68,
            "context_recall": 0.65,
        },
    )

    monkeypatch.setattr(admin_eval, "RESULTS_DIR", fake_dir)
    return fake_dir


class TestEvalCompareEndpoint:
    def test_compare_two_history_snapshots(self, client, admin_headers, fake_results_dir):
        """对比两个历史快照,返回 4 个 diff + improved/regressed 计数

        设计 diff:
          faithfulness       0.85 -> 0.88  (+0.03)  same  (abs < 0.05 阈值)
          answer_relevancy   0.85 -> 0.78  (-0.07)  down
          context_precision  0.72 -> 0.68  (-0.04)  same
          context_recall     0.50 -> 0.65  (+0.15)  up
        统计:same=2, down=1, up=1
        """
        res = client.get(
            "/api/admin/eval/compare",
            params={"base": "2026-06-08T23-26-02", "target": "2026-06-10T10-00-00"},
            headers=admin_headers,
        )
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["base"]["timestamp"] == "2026-06-08T23-26-02"
        assert data["target"]["timestamp"] == "2026-06-10T10-00-00"
        assert len(data["diffs"]) == 4

        # base 0.85 -> target 0.88 → +0.03,abs < 0.05 → same
        f_diff = next(d for d in data["diffs"] if d["name"] == "faithfulness")
        assert f_diff["base"] == 0.85
        assert f_diff["target"] == 0.88
        assert f_diff["change"] == pytest.approx(0.03, abs=1e-3)
        assert f_diff["direction"] == "same"

        # answer_relevancy -0.07 → down
        a_diff = next(d for d in data["diffs"] if d["name"] == "answer_relevancy")
        assert a_diff["direction"] == "down"

        # context_recall +0.15 → up
        c_diff = next(d for d in data["diffs"] if d["name"] == "context_recall")
        assert c_diff["direction"] == "up"

        # 统计:1 up / 1 down / 2 same
        assert data["improved"] == 1
        assert data["regressed"] == 1
        assert data["same"] == 2

    def test_compare_with_latest_keyword(self, client, admin_headers, fake_results_dir):
        """支持 'latest' 关键字指向 latest.json"""
        res = client.get(
            "/api/admin/eval/compare",
            params={"base": "2026-06-08T23-26-02", "target": "latest"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["target"]["timestamp"] == "2026-06-12T22-41-09"

    def test_compare_invalid_ts_format(self, client, admin_headers, fake_results_dir):
        """非法 ts 返回 400"""
        res = client.get(
            "/api/admin/eval/compare",
            params={"base": "not-a-timestamp", "target": "latest"},
            headers=admin_headers,
        )
        assert res.status_code == 400
        assert "格式无效" in res.json()["detail"]

    def test_compare_missing_snapshot(self, client, admin_headers, fake_results_dir):
        """快照不存在返回 404"""
        res = client.get(
            "/api/admin/eval/compare",
            params={"base": "2026-06-08T23-26-02", "target": "2026-06-09T00-00-00"},
            headers=admin_headers,
        )
        assert res.status_code == 404

    def test_compare_requires_auth(self, client, fake_results_dir):
        """无 admin token 返回 401"""
        res = client.get(
            "/api/admin/eval/compare",
            params={"base": "latest", "target": "latest"},
        )
        assert res.status_code in (401, 403)

    def test_compare_direction_within_threshold(self, client, admin_headers, fake_results_dir):
        """变化绝对值 < 0.05 判定为 same"""
        # 准备一个变化 0.04 的快照(在 0.05 阈值内)
        from app.api import admin_eval
        (admin_eval.RESULTS_DIR / "history" / "2026-06-09T10-00-00.json").write_text(
            json.dumps(
                {
                    "timestamp": "2026-06-09T10-00-00",
                    "aggregated": {
                        "faithfulness": 0.85 + 0.04,  # +0.04 → same
                        "answer_relevancy": 0.85,
                        "context_precision": 0.72,
                        "context_recall": 0.50,
                    },
                    "errors": [],
                    "total": 5,
                }
            ),
            encoding="utf-8",
        )
        res = client.get(
            "/api/admin/eval/compare",
            params={"base": "2026-06-08T23-26-02", "target": "2026-06-09T10-00-00"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        f_diff = next(d for d in data["diffs"] if d["name"] == "faithfulness")
        assert f_diff["direction"] == "same"
        assert data["same"] >= 1
