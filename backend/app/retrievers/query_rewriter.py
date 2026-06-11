"""查询改写器

把单条用户 query 改写成 N 个语义等价的检索变体，供多路召回合并使用。
失败/超时/空响应一律回退到 `[query]`，不抛异常给上层。
"""

import asyncio
import logging
import time
from pathlib import Path

from app.core.exceptions import ExternalServiceError
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "query_rewrite.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


class QueryRewriter:
    """把单条 query 改写成 N 个语义等价变体。

    返回的列表第 0 项永远是原 query，便于回退路径与可观测。
    """

    def __init__(
        self,
        llm: LLMService,
        n: int = 3,
        timeout_s: float = 5.0,
    ):
        if n < 1:
            raise ValueError("n must be >= 1")
        self.llm = llm
        self.n = n
        self.timeout_s = timeout_s

    def rewrite(self, query: str) -> list[str]:
        """同步入口：阻塞等 LLM 返回，返回 [原 query, 变体1, 变体2, ...]。

        失败/超时/空响应时返回 [query]，不抛异常。
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.arewrite(query))
        finally:
            loop.close()

    async def arewrite(self, query: str) -> list[str]:
        """异步入口：在线程池跑 LLM 调用 + 5s 超时。"""
        # N=1 表示无需改写，直接返回原 query
        if self.n == 1:
            return [query]
        start = time.time()
        try:
            prompt = _PROMPT_TEMPLATE.format(n=self.n)
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ]
            loop = asyncio.get_event_loop()
            raw = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.llm.chat(
                        messages, temperature=0.3, max_tokens=200
                    ),
                ),
                timeout=self.timeout_s,
            )
            variants = self._parse(raw, expected=self.n)
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(
                f"QueryRewriter: {len(variants)} 变体, {elapsed_ms}ms"
            )
            return [query] + variants
        except asyncio.TimeoutError:
            logger.warning(
                f"QueryRewriter: 超时 ({self.timeout_s}s), 回退原 query"
            )
            return [query]
        except ExternalServiceError as e:
            logger.warning(f"QueryRewriter: 外部服务失败, 回退原 query: {e}")
            return [query]
        except Exception as e:
            logger.warning(f"QueryRewriter: 未知异常, 回退原 query: {e}")
            return [query]

    @staticmethod
    def _parse(raw: str, expected: int) -> list[str]:
        """按行 split + strip + 去空行，截到 expected 个变体（不含原 query）。"""
        if not raw:
            return []
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        # 去掉可能的前缀编号（"1. xxx" / "1) xxx" / "- xxx" / "• xxx"）
        cleaned = []
        for line in lines:
            for prefix in ("1.", "2.", "3.", "4.", "5.", "1)", "2)", "3)", "4)", "5)", "-", "•", "*"):
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break
            if line:
                cleaned.append(line)
        return cleaned[:expected]
