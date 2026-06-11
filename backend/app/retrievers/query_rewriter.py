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

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# 每个 variant 的温度 + prompt 文件名（fallback 到 v1）
_PROMPT_FILES = {
    1: "query_rewrite_v1.txt",
    2: "query_rewrite_v2.txt",
    3: "query_rewrite_v3.txt",
    4: "query_rewrite_v4.txt",
    5: "query_rewrite_v5.txt",
}
_TEMP_BY_VARIANT = {1: 0.3, 2: 0.3, 3: 0.3, 4: 0.7, 5: 0.5}


def _load_prompt(variant: int) -> str:
    """加载指定 variant 的 Prompt 模板，找不到回退到 v1。"""
    filename = _PROMPT_FILES.get(variant) or _PROMPT_FILES[1]
    path = _PROMPTS_DIR / filename
    if not path.exists():
        # v1 兜底：找原 query_rewrite.txt
        fallback = _PROMPTS_DIR / "query_rewrite.txt"
        if fallback.exists():
            return fallback.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Prompt variant {variant} not found: {path}")
    return path.read_text(encoding="utf-8")


class QueryRewriter:
    """把单条 query 改写成 N 个语义等价变体。

    返回的列表第 0 项永远是原 query，便于回退路径与可观测。

    Args:
        llm: LLM 服务
        n: 变体数量（含原 query 共 N+1 个查询）
        timeout_s: 改写 LLM 超时
        prompt_variant: Prompt 变体编号 1..5，不同变体切不同温度
    """

    def __init__(
        self,
        llm: LLMService,
        n: int = 3,
        timeout_s: float = 5.0,
        prompt_variant: int = 1,
    ):
        if n < 1:
            raise ValueError("n must be >= 1")
        if prompt_variant not in _PROMPT_FILES:
            logger.warning(
                f"QueryRewriter: 未知 prompt_variant={prompt_variant}, 回退 v1"
            )
            prompt_variant = 1
        self.llm = llm
        self.n = n
        self.timeout_s = timeout_s
        self.prompt_variant = prompt_variant
        self.temperature = _TEMP_BY_VARIANT.get(prompt_variant, 0.3)
        self.prompt_template = _load_prompt(prompt_variant)

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
            prompt = self.prompt_template.format(n=self.n)
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ]
            loop = asyncio.get_running_loop()
            raw = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.llm.chat(
                        messages,
                        temperature=self.temperature,
                        max_tokens=200,
                    ),
                ),
                timeout=self.timeout_s,
            )
            variants = self._parse(raw, expected=self.n)
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(
                f"QueryRewriter: variant={self.prompt_variant} "
                f"{len(variants)} 变体, {elapsed_ms}ms"
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
