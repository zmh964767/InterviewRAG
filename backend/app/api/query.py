"""问答接口"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_rag_service
from app.models.schemas import QueryRequest, QueryResponse, SourceRef
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter()

# 对话存储（MVP 用内存，后续可换 Redis）
conversations: dict[str, list] = {}


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
    history = query_req.chat_history or conversations.get(conversation_id, [])

    if query_req.stream:
        return StreamingResponse(
            stream_generator(rag_service, query_req.question, history, conversation_id, request),
            media_type="text/event-stream",
        )

    # 普通返回
    result = await rag_service.query(
        question=query_req.question,
        chat_history=history,
    )

    # 更新对话历史
    history.append({"role": "user", "content": query_req.question})
    history.append({"role": "assistant", "content": result["answer"]})
    conversations[conversation_id] = history[-20:]  # 保留最近 10 轮

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

    修复 1：SSE 响应不带 response_model，移除 FastAPI 强校验。
    修复 2：用户切走时浏览器 abort 会触发 CancelledError，
            此时已生成的部分答案（partial answer）必须保存到
            conversations[] 字典，否则切回来就是空。
    修复 3：每次 yield 前检查 request.is_disconnected()，主动退出流。
            避免：LLM 已停止但客户端已断开 → yield 仍然触发 →
            Starlette 抛 "BodyStreamBuffer was aborted" 错误。
    """
    full_answer = ""
    try:
        gen = await rag_service.query_stream(
            question=question,
            chat_history=history,
        )
        async for chunk in gen:
            # 客户端断开（用户切走/导航）→ 主动退出循环，停止 LLM 流
            if await request.is_disconnected():
                logger.info(
                    f"客户端已断开，停止流式响应 (已生成 {len(full_answer)} chars)"
                )
                # 已生成的部分保存到 history
                if full_answer:
                    history.append({"role": "user", "content": question})
                    history.append({"role": "assistant", "content": full_answer + "…"})
                    conversations[conversation_id] = history[-20:]
                return  # 正常退出 generator
            full_answer += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        # 获取来源引用（从生成器对象读取，避免实例属性竞争）
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

        # 发送完成信号（附带来源引用）
        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'sources': source_refs}, ensure_ascii=False)}\n\n"

        # 正常完成：把完整问答存入 history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": full_answer})
        conversations[conversation_id] = history[-20:]

    except asyncio.CancelledError:
        # 前端主动关闭（用户切走/取消浏览器）
        # 重要：已生成的部分必须保存到 history
        if full_answer:
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": full_answer + "…"})
            conversations[conversation_id] = history[-20:]
            logger.info(
                f"流式被前端取消，已保存 partial answer ({len(full_answer)} chars) "
                f"to conversation {conversation_id}"
            )
        # 不 raise：避免触发 FastAPI 500
    except Exception as e:
        logger.error(f"流式生成异常: {e}", exc_info=True)
        try:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        except Exception:
            pass
