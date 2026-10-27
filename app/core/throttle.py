"""Adaptive concurrency limit (R-PIPE-5, ported from movies2vlib): halve after failures."""

import asyncio


class AdaptiveLimiter:
    """Async context manager bounding concurrent holders; `record(False)` shrinks the bound."""

    def __init__(
        self, limit: int, fail_threshold: int = 2, recover_after: int = 10
    ) -> None:
        self.limit = self.max_limit = limit
        self.fail_threshold = fail_threshold
        self.recover_after = recover_after
        self._successes = 0
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
        """Note an outcome; return the new limit when it changes.

        `fail_threshold` consecutive failures halve the limit; `recover_after` consecutive
        successes double it back toward the configured maximum.
        """
        if ok:
            self._failures = 0
            self._successes += 1
            if self._successes < self.recover_after or self.limit >= self.max_limit:
                return None
            self._successes = 0
            self.limit = min(self.max_limit, self.limit * 2)
            return self.limit
        self._successes = 0
        self._failures += 1
        if self._failures < self.fail_threshold or self.limit <= 1:
            return None
        self._failures = 0
        self.limit = max(1, self.limit // 2)
        return self.limit
