"""问答接口"""

import json
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import QueryRequest, QueryResponse, SourceRef
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter()

# 对话存储（MVP 用内存，后续可换 Redis）
conversations: dict[str, list] = {}

# 模块级单例，避免每次请求重新初始化
_rag_service: RAGService | None = None


def _get_rag_service() -> RAGService:
    """获取 RAG 服务单例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """问答接口，支持普通返回和 SSE 流式返回"""

    # 获取或创建对话 ID
    conversation_id = request.conversation_id or str(uuid.uuid4())
    # 优先使用前端传来的对话历史，否则从服务端存储读取
    history = request.chat_history or conversations.get(conversation_id, [])

    rag_service = _get_rag_service()

    if request.stream:
        return StreamingResponse(
            stream_generator(rag_service, request.question, history, conversation_id),
            media_type="text/event-stream",
        )

    # 普通返回
    result = await rag_service.query(
        question=request.question,
        chat_history=history,
    )

    # 更新对话历史
    history.append({"role": "user", "content": request.question})
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


async def stream_generator(rag_service, question, history, conversation_id):
    """SSE 流式生成器"""
    try:
        full_answer = ""

        async for chunk in rag_service.query_stream(
            question=question,
            chat_history=history,
        ):
            full_answer += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        # 获取来源引用（在 query_stream 中已计算并缓存在 _last_sources）
        sources = getattr(rag_service, "_last_sources", [])
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

        # 更新对话历史
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": full_answer})
        conversations[conversation_id] = history[-20:]

    except Exception as e:
        logger.error(f"流式生成异常: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
