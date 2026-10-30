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


def test_recovers_toward_the_configured_limit_after_a_success_streak():
    lim = AdaptiveLimiter(4, fail_threshold=2, recover_after=3)
    lim.record(False), lim.record(False)
    assert lim.limit == 2
    assert [lim.record(True) for _ in range(3)] == [None, None, 4]
    assert lim.limit == 4
    assert all(
        lim.record(True) is None for _ in range(10)
    )  # never above the configured max


def test_a_failure_resets_the_recovery_streak():
    lim = AdaptiveLimiter(4, fail_threshold=1, recover_after=3)
    lim.record(False)
    lim.record(True), lim.record(True)
    lim.record(False)
    lim.record(True), lim.record(True)
    assert lim.limit == 1


def test_orchestrator_records_one_execute_outcome_per_item():
    from unittest.mock import MagicMock

    from app.core.orchestrator import PipelineOrchestrator

    o = PipelineOrchestrator.__new__(PipelineOrchestrator)
    o._recorded, o._exec, o.trace, o.logger = (
        set(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    o._exec.record.return_value = None
    o._record_execute(False, "a")
    o._record_execute(False, "a")  # _guarded after execute.run already recorded it
    assert o._exec.record.call_count == 1
    o._record_execute(False, "b")
    assert o._exec.record.call_count == 2
