"""Items waiting for a human are not polled; auto-approve types still are."""

from unittest.mock import AsyncMock

import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem, MediaType
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _polled(tmp_path, auto_approve):
    cfg = make_config(tmp_path)
    cfg.auto_approve_types = frozenset(auto_approve)
    engine, factory = await make_session_factory(tmp_path)
    async with factory() as s:
        s.add(
            MediaItem(
                id="a",
                source_path="/in/a.mp3",
                state=FileState.planned,
                media_type=MediaType.music,
            )
        )
        await s.commit()
    orch = PipelineOrchestrator(factory, cfg)
    orch._guarded = AsyncMock(return_value=False)
    await orch.run_once()
    await engine.dispose()
    return orch._guarded.await_count


async def test_planned_item_awaiting_review_is_not_polled(tmp_path):
    assert await _polled(tmp_path, []) == 0


async def test_planned_item_of_an_auto_approve_type_is_polled(tmp_path):
    assert await _polled(tmp_path, ["music"]) == 1
