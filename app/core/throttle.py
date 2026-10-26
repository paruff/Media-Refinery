"""Adaptive concurrency limit (R-PIPE-5, ported from movies2vlib): halve after failures."""

import asyncio


class AdaptiveLimiter:
    """Async context manager bounding concurrent holders; `record(False)` shrinks the bound."""

    def __init__(self, limit: int, fail_threshold: int = 2) -> None:
        self.limit = limit
        self.fail_threshold = fail_threshold
        self._active = 0
        self._failures = 0
        self._cond = asyncio.Condition()

    async def __aenter__(self) -> None:
        async with self._cond:
            await self._cond.wait_for(lambda: self._active < self.limit)
            self._active += 1

    async def __aexit__(self, *exc) -> None:
        async with self._cond:
            self._active -= 1
            self._cond.notify_all()

    def record(self, ok: bool) -> int | None:
        """Note an outcome; return the new limit when `fail_threshold` consecutive failures halve it."""
        if ok:
            self._failures = 0
            return None
        self._failures += 1
        if self._failures < self.fail_threshold or self.limit <= 1:
            return None
        self._failures = 0
        self.limit = max(1, self.limit // 2)
        return self.limit
