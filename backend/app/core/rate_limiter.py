"""共享限流模块

- get_client_ip(): 提取真实客户端 IP（支持受信代理 XFF）
- PerIPRateLimiter: 基于滑动窗口的 per-IP 限流器
"""

import threading
import time

from fastapi import Request


def get_client_ip(request: Request, trusted_proxies: list[str]) -> str:
    """提取客户端真实 IP。

    - 直接连接时使用 request.client.host
    - 仅当 trusted_proxies 非空且 direct_ip 在信任列表中时才读取 X-Forwarded-For
    """
    direct_ip = request.client.host if request.client else "unknown"

    if trusted_proxies and direct_ip in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # XFF 格式: client, proxy1, proxy2 — 取第一个
            return forwarded.split(",")[0].strip()

    return direct_ip


class PerIPRateLimiter:
    """Per-IP 滑动窗口限流器（线程安全）"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._records: dict[str, tuple[int, float]] = {}  # ip -> (count, window_start)
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        """检查 IP 是否允许通过。返回 True=允许，False=应返回 429。"""
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)

            record = self._records.get(ip)
            if record is None:
                # 该 IP 没有记录，创建新窗口
                self._records[ip] = (1, now)
                return True

            count, window_start = record

            # 窗口已过期，重置
            if now - window_start >= self.window_seconds:
                self._records[ip] = (1, now)
                return True

            # 窗口内检查
            if count >= self.max_requests:
                return False

            self._records[ip] = (count + 1, window_start)
            return True

    def reset(self, ip: str) -> None:
        """移除 IP 的限流记录（用于登录成功等场景）。"""
        with self._lock:
            self._records.pop(ip, None)

    def _evict_expired(self, now: float) -> None:
        """清理所有已过期的记录。调用方需持有 _lock。"""
        expired = [
            ip for ip, (_, start) in self._records.items()
            if now - start >= self.window_seconds
        ]
        for ip in expired:
            del self._records[ip]
