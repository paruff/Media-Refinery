import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.orchestrator import STATE_MAP, PipelineOrchestrator


def _db(items):
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


def _item(state, **kw):
    return SimpleNamespace(id="i1", state=state, retry_count=0, **kw)


@pytest.mark.asyncio
async def test_recover_inflight_moves_executing_to_planned():
    item = _item("executing")
    db = _db([item])
    await PipelineOrchestrator(db)._recover_inflight()
    assert item.state == "planned"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["pending", "scanned"])
async def test_generic_service_advances_state(state):
    item = _item(state)
    orch = PipelineOrchestrator(_db([item]))
    with patch("asyncio.sleep", AsyncMock()):
        await orch._process_actionable_items()
    assert item.state == STATE_MAP[state]["next"]


@pytest.mark.asyncio
async def test_enricher_and_executor_use_semaphores():
    enrich, execute = _item("classified"), _item("planned")
    orch = PipelineOrchestrator(_db([enrich, execute]))
    with patch("asyncio.sleep", AsyncMock()):
        await orch._process_actionable_items()
    assert enrich.state == "enriched"
    assert execute.state == "executing"
    assert execute.celery_task_id == "fake-task-id"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("celery_state", "expected"),
    [
        ("SUCCESS", "executed"),
        ("FAILURE", "error"),
        ("PENDING", "planned"),
    ],
)
async def test_executor_monitors_celery_result(celery_state, expected):
    item = _item("planned", celery_task_id="t1")
    orch = PipelineOrchestrator(_db([item]))
    with patch(
        "app.core.orchestrator.AsyncResult",
        return_value=SimpleNamespace(state=celery_state),
    ):
        await orch._dispatch(item, "executor", STATE_MAP["planned"])
    assert item.state == expected


@pytest.mark.asyncio
async def test_failure_over_retry_limit_is_error():
    item = _item("planned", celery_task_id="t1")
    item.retry_count = 3
    orch = PipelineOrchestrator(_db([item]))
    with patch(
        "app.core.orchestrator.AsyncResult",
        return_value=SimpleNamespace(state="REVOKED"),
    ):
        await orch._dispatch(item, "executor", STATE_MAP["planned"])
    assert (item.state, item.retry_count) == ("error", 4)


@pytest.mark.asyncio
async def test_dispatch_exception_marks_failure():
    item = _item("pending")
    orch = PipelineOrchestrator(_db([item]))
    with patch("asyncio.sleep", AsyncMock(side_effect=RuntimeError("boom"))):
        await orch._dispatch(item, "scanner", STATE_MAP["pending"])
    assert (item.state, item.retry_count) == ("error", 1)


@pytest.mark.asyncio
async def test_run_forever_survives_loop_error_and_stops():
    orch = PipelineOrchestrator(_db([]), poll_interval=0)
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        orch.running = False
        raise RuntimeError("x")

    orch._process_actionable_items = flaky
    await asyncio.wait_for(orch.run_forever(), 2)
    assert calls == 1
