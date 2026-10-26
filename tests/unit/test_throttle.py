import asyncio

import pytest

from app.core.throttle import AdaptiveLimiter


def test_halves_after_consecutive_failures_and_success_resets():
    lim = AdaptiveLimiter(4, fail_threshold=2)
    assert lim.record(False) is None
    assert lim.record(True) is None  # streak broken
    assert lim.record(False) is None
    assert lim.record(False) == 2
    assert lim.record(False) is None and lim.record(False) == 1
    assert lim.record(False) is None and lim.record(False) is None  # floor is 1
    assert lim.limit == 1


@pytest.mark.asyncio
async def test_bounds_concurrent_holders():
    lim = AdaptiveLimiter(2)
    active = peak = 0

    async def work():
        nonlocal active, peak
        async with lim:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(work() for _ in range(6)))
    assert peak == 2
