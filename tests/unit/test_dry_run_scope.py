"""#90 (R-SAFE-4): DRY_RUN must not publish/archive items already past approval, nor touch work files in recover()."""

import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem, MediaType
from app.models.saga import SagaFileMoveLog, SagaLogStatus
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _seed(factory, state, name="a.mp3"):
    async with factory() as s:
        s.add(
            MediaItem(
                id=name,
                source_path=str(f"/in/{name}"),
                state=state,
                media_type=MediaType.music,
            )
        )
        await s.commit()


@pytest.mark.parametrize(
    "state",
    [FileState.approved, FileState.executed, FileState.verified, FileState.published],
)
async def test_dry_run_does_not_advance_items_past_planning(tmp_path, state):
    cfg = make_config(tmp_path)
    cfg.dry_run = True
    engine, factory = await make_session_factory(tmp_path)
    await _seed(factory, state)
    orch = PipelineOrchestrator(factory, cfg)

    assert await orch.run_once() == 0

    async with factory() as s:
        assert (await s.get(MediaItem, "a.mp3")).state == state
    assert not cfg.archive_dir.exists() and not cfg.quarantine_dir.exists()
    await engine.dispose()


async def test_dry_run_recover_leaves_work_files_and_sagas_alone(tmp_path):
    cfg = make_config(tmp_path)
    cfg.dry_run = True
    engine, factory = await make_session_factory(tmp_path)
    await _seed(factory, FileState.executing)
    work = cfg.work_dir / "a.mp3"
    work.mkdir(parents=True)
    (work / "out.mp3").write_bytes(b"partial")
    tmp = tmp_path / "publish.tmp"
    tmp.write_bytes(b"x")
    async with factory() as s:
        s.add(
            SagaFileMoveLog(
                plan_id="p",
                src_path="s",
                tmp_path=str(tmp),
                dest_path="d",
                status=SagaLogStatus.prepared,
            )
        )
        await s.commit()

    await PipelineOrchestrator(factory, cfg).recover()

    assert (work / "out.mp3").exists() and tmp.exists()
    async with factory() as s:
        assert (await s.get(MediaItem, "a.mp3")).state == FileState.executing
    await engine.dispose()
