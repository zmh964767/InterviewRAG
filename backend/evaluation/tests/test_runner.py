"""evaluation/runner.py 单测

覆盖：
- TokenBucket 限流桶（初始容量、acquire 扣减）
- RAGAS checkpoint 加载/保存（无文件、往返、新建）
- run_comparison_evaluation（reranker 不可用跳过 plan_c、plan_b 调 hybrid）
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from evaluation import runner
from evaluation.runner import (
    TokenBucket,
    _load_ragas_checkpoint,
    _save_ragas_checkpoint,
    RAGAS_CHECKPOINT_PATH,
)


# =====================================================================
# TokenBucket
# =====================================================================


def test_token_bucket_initial_capacity():
    """新建 TokenBucket(rate_per_min=60)：tokens == 60（capacity 默认 = rate）"""
    bucket = TokenBucket(rate_per_min=60)
    assert bucket.tokens == 60
    assert bucket.capacity == 60


@pytest.mark.asyncio
async def test_token_bucket_acquire_drains():
    """acquire(5) 扣减 5 个 token"""
    bucket = TokenBucket(rate_per_min=60, capacity=60)
    assert bucket.tokens == 60
    await bucket.acquire(5)
    assert bucket.tokens == 55


# =====================================================================
# RAGAS checkpoint
# =====================================================================


def test_load_checkpoint_no_file(monkeypatch, tmp_path):
    """checkpoint 文件不存在：返回 None"""
    fake_path = tmp_path / "_ragas_checkpoint.json"
    monkeypatch.setattr(runner, "RAGAS_CHECKPOINT_PATH", fake_path)
    assert _load_ragas_checkpoint() is None


def test_load_and_save_roundtrip(monkeypatch, tmp_path):
    """save 后 load：数据完全一致（JSON 序列化把 int key 变成 str key）"""
    fake_path = tmp_path / "_ragas_checkpoint.json"
    monkeypatch.setattr(runner, "RAGAS_CHECKPOINT_PATH", fake_path)

    aggregated = {"faithfulness": 0.9, "answer_relevancy": 0.8}
    per_item = {0: {"f": 0.9}, 1: {"f": 0.85}}
    successful_ids = ["id1", "id2"]

    _save_ragas_checkpoint(aggregated, per_item, successful_ids)
    loaded = _load_ragas_checkpoint()

    assert loaded is not None
    assert loaded["aggregated"] == aggregated
    # JSON 序列化会把 int key 转成 str（json 规范），所以这里比对 str key 版
    assert loaded["per_item"] == {str(k): v for k, v in per_item.items()}
    assert loaded["successful_ids"] == successful_ids


def test_save_checkpoint_creates_file(monkeypatch, tmp_path):
    """save 后文件存在 + 可被 json.loads 解析"""
    fake_path = tmp_path / "_ragas_checkpoint.json"
    monkeypatch.setattr(runner, "RAGAS_CHECKPOINT_PATH", fake_path)
    assert not fake_path.exists()

    _save_ragas_checkpoint({"f": 0.5}, {"a": 1}, ["x"])

    assert fake_path.exists()
    data = json.loads(fake_path.read_text(encoding="utf-8"))
    assert data["aggregated"] == {"f": 0.5}
    assert data["successful_ids"] == ["x"]


# =====================================================================
# run_comparison_evaluation
# =====================================================================


# 提前 import：触发依赖（让 monkeypatch 字符串路径不需重新解析）
# 关键：runner.py 用的是 `from app.xxx import Yyy`（函数内 local import），
# 所以必须 patch 这些类在原始模块里的属性。
import app.core.vectorstore as _vs_mod
import app.rerankers.bge_reranker as _rerank_mod
import app.retrievers.hybrid_retriever as _hybrid_mod
import app.retrievers.small_to_big as _s2b_mod
import app.services.llm_service as _llm_mod
import app.retrievers.query_rewriter as _qr_mod
import app.retrievers.multi_query_retriever as _mqr_mod
import app.config as _config_mod


@pytest.mark.asyncio
async def test_comparison_skips_plan_c_when_reranker_unavailable(monkeypatch):
    """reranker.is_available() == False：返回 dict 不含 'C_混合+Rerank'"""
    # mock 所有子服务（避免真实网络/模型加载）
    fake_vector_store = MagicMock()
    fake_hybrid = MagicMock()
    fake_hybrid.retrieve = MagicMock(return_value=[])
    fake_s2b = MagicMock()
    fake_s2b.retrieve = MagicMock(return_value=[])
    fake_reranker = MagicMock()
    fake_reranker.is_available = MagicMock(return_value=False)  # 关键：不可用
    fake_llm = MagicMock()
    fake_rewriter = MagicMock()
    fake_mqr = MagicMock()
    fake_mqr.set_rewriter = MagicMock()

    # runner.py 是函数内 `from app.xxx import Yyy`，必须 patch 原模块的属性
    monkeypatch.setattr(_vs_mod, "VectorStore", lambda *a, **kw: fake_vector_store)
    monkeypatch.setattr(_rerank_mod, "BGEReranker", lambda *a, **kw: fake_reranker)
    monkeypatch.setattr(_hybrid_mod, "HybridRetriever", lambda *a, **kw: fake_hybrid)
    monkeypatch.setattr(_s2b_mod, "SmallToBigRetriever", lambda *a, **kw: fake_s2b)
    monkeypatch.setattr(_llm_mod, "LLMService", lambda *a, **kw: fake_llm)
    monkeypatch.setattr(_qr_mod, "QueryRewriter", lambda *a, **kw: fake_rewriter)
    monkeypatch.setattr(_mqr_mod, "MultiQueryRetriever", lambda *a, **kw: fake_mqr)
    monkeypatch.setattr(_config_mod, "get_settings", lambda: MagicMock(
        multi_query_n=3, multi_query_timeout_s=5, query_rewrite_prompt_variant=1,
        retrieval_top_k=5,
    ))

    items = [{"id": "q1", "question": "什么是 RAG？"}]
    result = await runner.run_comparison_evaluation(items)

    assert "C_混合+Rerank" not in result
    # 其他 4 个 plan 仍应在
    for plan in ("A_纯向量", "B_混合检索", "D_小块检索大块生成", "E_多路改写混合"):
        assert plan in result


@pytest.mark.asyncio
async def test_comparison_plan_b_calls_hybrid(monkeypatch):
    """plan_b 调 hybrid_retriever.retrieve（同步）"""
    fake_vector_store = MagicMock()
    # plan_a 会调 vector_store.query，给个空返回
    fake_vector_store.query = MagicMock(return_value={"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]})

    # plan_b 走 hybrid_retriever.retrieve，mock 塞返回
    fake_hybrid = MagicMock()
    fake_hybrid.retrieve = MagicMock(return_value=[])

    fake_s2b = MagicMock()
    fake_s2b.retrieve = MagicMock(return_value=[])

    fake_reranker = MagicMock()
    fake_reranker.is_available = MagicMock(return_value=False)
    fake_llm = MagicMock()
    fake_rewriter = MagicMock()
    fake_mqr = MagicMock()
    fake_mqr.set_rewriter = MagicMock()

    monkeypatch.setattr(_vs_mod, "VectorStore", lambda *a, **kw: fake_vector_store)
    monkeypatch.setattr(_rerank_mod, "BGEReranker", lambda *a, **kw: fake_reranker)
    monkeypatch.setattr(_hybrid_mod, "HybridRetriever", lambda *a, **kw: fake_hybrid)
    monkeypatch.setattr(_s2b_mod, "SmallToBigRetriever", lambda *a, **kw: fake_s2b)
    monkeypatch.setattr(_llm_mod, "LLMService", lambda *a, **kw: fake_llm)
    monkeypatch.setattr(_qr_mod, "QueryRewriter", lambda *a, **kw: fake_rewriter)
    monkeypatch.setattr(_mqr_mod, "MultiQueryRetriever", lambda *a, **kw: fake_mqr)
    monkeypatch.setattr(_config_mod, "get_settings", lambda: MagicMock(
        multi_query_n=3, multi_query_timeout_s=5, query_rewrite_prompt_variant=1,
        retrieval_top_k=5,
    ))

    items = [{"id": "q1", "question": "test"}]
    await runner.run_comparison_evaluation(items)

    # plan_b 调了 hybrid_retriever.retrieve（注意：plan_c 也会调，但 reranker 不可用所以 plan_c 不存在）
    # plan_e 失败回退时也会调 hybrid，所以 call_count >= 1
    assert fake_hybrid.retrieve.call_count >= 1
