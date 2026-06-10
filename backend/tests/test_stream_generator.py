"""stream_generator 单元测试

覆盖：
- 正常流式完成 → 数据帧 + done 信号 + history 保存
- CancelledError → partial answer 保存到 conversations
- 异常 → error SSE 帧 yield
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.query import stream_generator, conversations


# ---- helpers ----

def _make_question():
    return {"question": "测试问题", "chat_history": [], "stream": True}


class FakeStreamGen:
    """模拟 rag_service.query_stream 的异步生成器"""

    def __init__(self, chunks: list[str], *, sources=None, exc=None):
        self._chunks = chunks
        self._exc = exc
        self.sources = sources or []

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._exc:
            raise self._exc
        if self._chunks:
            return self._chunks.pop(0)
        raise StopAsyncIteration


# ---- 测试 ----

class TestStreamGeneratorNormal:
    """正常流式完成"""

    @pytest.mark.asyncio
    async def test_yields_data_frames_and_done(self):
        """应 yield 多个 data 帧 + 一个 done 帧"""
        gen = FakeStreamGen(chunks=["hello", " world"], sources=[
            {"id": "s1", "question": "q1", "score": 0.9, "category": "LLM"},
        ])
        rag_service = MagicMock()
        rag_service.query_stream.return_value = gen

        history = []
        conv_id = "conv-test-1"

        results = []
        async for frame in stream_generator(rag_service, "测试问题", history, conv_id):
            results.append(frame)

        # 应有 2 个 data chunk + 1 个 done = 3 帧
        assert len(results) == 3

        # 第一帧是 data: chunk
        first = json.loads(results[0].removeprefix("data: ").strip())
        assert first == {"content": "hello"}

        # 最后一帧是 done
        last = json.loads(results[-1].removeprefix("data: ").strip())
        assert last["done"] is True
        assert last["conversation_id"] == conv_id
        assert len(last["sources"]) == 1

    @pytest.mark.asyncio
    async def test_saves_to_history(self):
        """正常完成时 history 应追加 Q&A 对"""
        gen = FakeStreamGen(chunks=["答案"])
        rag_service = MagicMock()
        rag_service.query_stream.return_value = gen

        history = []
        async for _ in stream_generator(rag_service, "Q", history, "c1"):
            pass

        assert history == [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "答案"},
        ]

    @pytest.mark.asyncio
    async def test_saves_to_conversations_dict(self):
        """正常完成时 conversations[conv_id] 应被更新"""
        gen = FakeStreamGen(chunks=["ok"])
        rag_service = MagicMock()
        rag_service.query_stream.return_value = gen

        history = []
        async for _ in stream_generator(rag_service, "Q", history, "c2"):
            pass

        assert "c2" in conversations
        assert len(conversations["c2"]) == 2


class TestStreamGeneratorCancelledError:
    """CancelledError：用户中途切走"""

    @pytest.mark.asyncio
    async def test_partial_answer_saved(self):
        """CancelledError 时 partial answer 应保存（带…后缀）"""
        # 模拟：yield 一个 chunk 后抛 CancelledError
        async def gen_that_cancels():
            yield "partial"
            raise asyncio.CancelledError()

        rag_service = MagicMock()
        rag_service.query_stream.return_value = gen_that_cancels()

        history = []
        conv_id = "cancelled-1"

        # stream_generator 吞掉 CancelledError，不 raise
        results = []
        async for frame in stream_generator(rag_service, "Q", history, conv_id):
            results.append(frame)

        # 只有 1 个 data chunk（partial），没有 done 帧
        assert len(results) == 1
        first = json.loads(results[0].removeprefix("data: ").strip())
        assert first == {"content": "partial"}

        # history 保存了 partial answer（带…）
        assert history[1]["content"] == "partial…"

        # conversations 被更新
        assert conv_id in conversations


class TestStreamGeneratorException:
    """非 CancelledError 的其他异常"""

    @pytest.mark.asyncio
    async def test_yields_error_frame(self):
        """异常时应 yield error SSE 帧，不 raise"""
        async def gen_that_errors():
            yield "boom"
            raise ValueError("LLM 服务挂了")

        rag_service = MagicMock()
        rag_service.query_stream.return_value = gen_that_errors()

        history = []
        results = []
        async for frame in stream_generator(rag_service, "Q", history, "e1"):
            results.append(frame)

        # data chunk + error 帧
        assert len(results) == 2
        error_frame = json.loads(results[-1].removeprefix("data: ").strip())
        assert "error" in error_frame
        assert "LLM 服务挂了" in error_frame["error"]

    @pytest.mark.asyncio
    async def test_history_not_saved_on_error(self):
        """异常时 history 不应被追加"""
        async def gen_that_errors():
            raise RuntimeError("boom")

        rag_service = MagicMock()
        rag_service.query_stream.return_value = gen_that_errors()

        history = []
        async for _ in stream_generator(rag_service, "Q", history, "e2"):
            pass

        assert len(history) == 0
