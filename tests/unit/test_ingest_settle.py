"""/scan must not import a file that is still being copied into the drop folder."""

import asyncio

import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.services.refinery import Refinery
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_ingest_with_settle_skips_files_that_change_meanwhile(tmp_path):
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    steady, growing = cfg.input_dir / "steady.mp3", cfg.input_dir / "growing.mp3"
    steady.write_bytes(b"done")
    growing.write_bytes(b"part")

    async def keep_copying():
        await asyncio.sleep(0.05)
        growing.write_bytes(b"part and more")

    refinery = Refinery(PipelineOrchestrator(factory, cfg))
    _, ids = await asyncio.gather(
        keep_copying(), refinery.ingest(cfg.input_dir, settle=0.2)
    )
    assert len(ids) == 1  # only steady.mp3
    await engine.dispose()
