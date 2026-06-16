"""stream_generator 单元测试

覆盖：
- 正常流式完成 → 数据帧 + done 信号 + history 保存
- CancelledError → partial answer 保存到 conversations
- 异常 → error SSE 帧 yield

注：rag_service.query_stream 现在是 coroutine（用 await 获取 _StreamWithSources），
    所以 mock 用 AsyncMock(return_value=gen) 模拟 `await query_stream(...)` 的结果。
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.query import stream_generator, conversation_store as conversations


# ---- helpers ----

class FakeRequest:
    """模拟 FastAPI Request：永不 disconnect（用于测试正常完成路径）"""
    async def is_disconnected(self) -> bool:
        return False


class DisconnectingRequest:
    """模拟 FastAPI Request：返回 True 模拟 client 断开"""
    def __init__(self):
        self.call_count = 0
    async def is_disconnected(self) -> bool:
        self.call_count += 1
        return self.call_count >= 2  # 第 2 次检查时返回 True（第一个 yield 之后）

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
        rag_service.query_stream = AsyncMock(return_value=gen)

        history = []
        conv_id = "conv-test-1"

        results = []
        async for frame in stream_generator(rag_service, "测试问题", history, conv_id, FakeRequest()):
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
        rag_service.query_stream = AsyncMock(return_value=gen)

        history = []
        async for _ in stream_generator(rag_service, "Q", history, "c1", FakeRequest()):
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
        rag_service.query_stream = AsyncMock(return_value=gen)

        history = []
        async for _ in stream_generator(rag_service, "Q", history, "c2", FakeRequest()):
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
        rag_service.query_stream = AsyncMock(return_value=gen_that_cancels())

        history = []
        conv_id = "cancelled-1"

        # stream_generator 吞掉 CancelledError，不 raise
        results = []
        async for frame in stream_generator(rag_service, "Q", history, conv_id, FakeRequest()):
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
        rag_service.query_stream = AsyncMock(return_value=gen_that_errors())

        history = []
        results = []
        async for frame in stream_generator(rag_service, "Q", history, "e1", FakeRequest()):
            results.append(frame)

        # data chunk + error 帧
        assert len(results) == 2
        error_frame = json.loads(results[-1].removeprefix("data: ").strip())
        assert "error" in error_frame
        assert error_frame["error"] == "生成异常，请重试"

    @pytest.mark.asyncio
    async def test_history_not_saved_on_error(self):
        """异常时 history 不应被追加"""
        async def gen_that_errors():
            raise RuntimeError("boom")

        rag_service = MagicMock()
        rag_service.query_stream = AsyncMock(return_value=gen_that_errors())

        history = []
        async for _ in stream_generator(rag_service, "Q", history, "e2", FakeRequest()):
            pass

        assert len(history) == 0


class TestStreamGeneratorClientDisconnect:
    """客户端断开（用户在流式中途切走/关闭页面）"""

    @pytest.mark.asyncio
    async def test_disconnect_stops_stream_and_saves_partial(self):
        """第一次 yield 后客户端断开 → 立即退出流，partial 保存"""
        # 模拟：yield 多个 chunk，让 disconnect 在第 2 次 yield 之前触发
        async def gen_long():
            for c in ['chunk1', 'chunk2', 'chunk3', 'chunk4']:
                yield c

        rag_service = MagicMock()
        rag_service.query_stream = AsyncMock(return_value=gen_long())

        history = []
        conv_id = "disconnect-1"

        results = []
        async for frame in stream_generator(rag_service, "Q", history, conv_id, DisconnectingRequest()):
            results.append(frame)

        # 只 yield 了 1 个 chunk（disconnectRequest 在第一次 yield 后断开，
        # 下一次循环开始时 is_disconnected() 返回 True）
        # 实际行为：chunk1 已 yield，下次循环 is_disconnected()=True → return
        # 所以结果是 1 个 data frame
        assert len(results) == 1

        # partial 保存到 history（带 …）
        assert history[1]["content"].endswith("…")
        assert "chunk1" in history[1]["content"]

        # conversations 更新
        assert conv_id in conversations
