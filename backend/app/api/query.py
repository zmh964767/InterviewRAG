"""问答接口"""

import asyncio
import json
import logging
import uuid
from collections import OrderedDict

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_rag_service
from app.models.schemas import QueryRequest, QueryResponse, SourceRef
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter()


class ConversationStore:
    """LRU 对话存储，上限 max_size，淘汰最久未访问的对话。

    提供 dict-like 接口（__getitem__, __setitem__, __contains__, keys, get），
    保证现有代码和测试兼容。
    """

    def __init__(self, max_size: int = 100):
        self._max_size = max_size
        self._store: OrderedDict[str, list] = OrderedDict()

    def get(self, cid: str, default: list | None = None) -> list | None:
        """读取对话历史，命中时更新 LRU 顺序。"""
        if cid in self._store:
            self._store.move_to_end(cid)
            return self._store[cid]
        return default

    def put(self, cid: str, history: list) -> None:
        """写入对话历史，超限时淘汰最久未访问的。"""
        self._store[cid] = history
        self._store.move_to_end(cid)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def __contains__(self, cid: str) -> bool:
        return cid in self._store

    def __getitem__(self, cid: str) -> list:
        self._store.move_to_end(cid)
        return self._store[cid]

    def __setitem__(self, cid: str, value: list) -> None:
        self.put(cid, value)

    def keys(self):
        return self._store.keys()


# 对话存储（MVP 用内存 LRU，后续可换 Redis）
conversation_store = ConversationStore()


@router.post("/query")
async def query_endpoint(
    request: Request,
    query_req: QueryRequest = Body(...),
    rag_service: RAGService = Depends(get_rag_service),
):
    """问答接口，支持普通返回和 SSE 流式返回

    修复：移除 response_model，因为 SSE 响应（text/event-stream）
    和 Pydantic JSON 模型不兼容，FastAPI 会强制校验 SSE 响应，
    导致 'There was an error parsing the body' 错误。
    """

    # 获取或创建对话 ID
    conversation_id = query_req.conversation_id or str(uuid.uuid4())
    # 优先使用前端传来的对话历史，否则从服务端存储读取
    history = query_req.chat_history or conversation_store.get(conversation_id, [])

    if query_req.stream:
        response = StreamingResponse(
            stream_generator(rag_service, query_req.question, history, conversation_id, request),
            media_type="text/event-stream",
        )
        response.headers["Cache-Control"] = "no-cache, no-transform"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    # 普通返回
    result = await rag_service.query(
        question=query_req.question,
        chat_history=history,
    )

    # 更新对话历史
    history.append({"role": "user", "content": query_req.question})
    history.append({"role": "assistant", "content": result["answer"]})
    conversation_store[conversation_id] = history[-20:]  # 保留最近 10 轮

    return QueryResponse(
        answer=result["answer"],
        sources=[
            SourceRef(
                question_id=s["id"],
                question_text=s["question"],
                score=s["score"],
                category=s["category"],
            )
            for s in result["sources"]
        ],
        conversation_id=conversation_id,
    )


async def stream_generator(rag_service, question, history, conversation_id, request: Request):
    """SSE 流式生成器

    断开处理统一在 finally 中：is_disconnected / CancelledError 只设 flag，
    finally 块根据 flag 决定保存完整或 partial answer，消除重复代码。
    """
    full_answer = ""
    completed = False  # True → 正常完成；False → 断开/取消（partial）

    try:
        gen = await rag_service.query_stream(
            question=question,
            chat_history=history,
        )
        async for chunk in gen:
            if await request.is_disconnected():
                logger.info(
                    f"客户端已断开，停止流式响应 (已生成 {len(full_answer)} chars)"
                )
                return
            full_answer += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        # 获取来源引用
        sources = getattr(gen, "sources", [])
        source_refs = [
            {
                "question_id": s["id"],
                "question_text": s["question"],
                "score": s["score"],
                "category": s["category"],
            }
            for s in sources
        ]

        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'sources': source_refs}, ensure_ascii=False)}\n\n"
        completed = True

    except asyncio.CancelledError:
        logger.info(
            f"流式被前端取消，保存 partial answer ({len(full_answer)} chars) "
            f"to conversation {conversation_id}"
        )
    except Exception as e:
        logger.error(f"流式生成异常: {e}", exc_info=True)
        try:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        except Exception:
            pass
        return  # 异常时不保存 history
    finally:
        if full_answer:
            if completed:
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": full_answer})
            else:
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": full_answer + "…"})
            conversation_store[conversation_id] = history[-20:]
