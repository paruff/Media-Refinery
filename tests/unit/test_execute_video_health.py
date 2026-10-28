"""G3/G4 review: corrupt media must not shrink the worker pool; inconclusive health != corrupt; stderr is kept."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
)
from app.pipeline import execute
from app.pipeline.types.video import VideoStrategy
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _setup(tmp_path, name="m.mkv"):
    cfg = make_config(tmp_path, max_concurrent_execute=4, throttle_after_failures=2)
    engine, factory = await make_session_factory(tmp_path)
    src = cfg.input_dir / name
    src.write_bytes(b"video")
    async with factory() as s:
        s.add(
            MediaItem(
                id=name,
                source_path=str(src),
                state=FileState.approved,
                media_type=MediaType.movie,
                video_codec="h264",
            )
        )
        s.add(
            NormalizationPlan(
                media_item_id=name,
                target_path=str(cfg.movies_root / "M (2020)" / "M (2020).mkv"),
                original_hash=name,
                ffmpeg_args=["-c", "copy"],
            )
        )
        await s.commit()
    return cfg, factory, engine


async def test_corrupt_files_do_not_halve_the_worker_pool(tmp_path):
    cfg, factory, engine = await _setup(tmp_path, "a.mkv")
    orch = PipelineOrchestrator(factory, cfg)
    with (
        patch(
            "app.pipeline.execute.health_check",
            return_value=(False, "ffmpeg_decode_errors"),
        ),
        patch("app.pipeline.execute.repair_remux", return_value=None),
    ):
        for n in ("a.mkv", "b.mkv", "c.mkv"):
            if n != "a.mkv":
                async with factory() as s:
                    s.add(
                        MediaItem(
                            id=n,
                            source_path=str(cfg.input_dir / n),
                            state=FileState.approved,
                            media_type=MediaType.movie,
                            video_codec="h264",
                        )
                    )
                    s.add(
                        NormalizationPlan(
                            media_item_id=n,
                            target_path=str(cfg.movies_root / n),
                            original_hash=n,
                            ffmpeg_args=[],
                        )
                    )
                    await s.commit()
            await execute.run(orch, n)
    async with factory() as s:
        assert (await s.get(MediaItem, "a.mkv")).state == FileState.quarantined
    assert orch._exec.limit == 4
    await engine.dispose()


async def test_inconclusive_health_check_proceeds_to_conversion(tmp_path):
    cfg, factory, engine = await _setup(tmp_path)
    orch = PipelineOrchestrator(factory, cfg)

    async def fake_ffmpeg(source, args, out):
        Path(out).write_bytes(b"converted")
        return 0, "", ""

    with (
        patch(
            "app.pipeline.execute.health_check",
            return_value=(False, "healthcheck_timeout"),
        ),
        patch("app.pipeline.execute.repair_remux") as repair,
        patch.object(orch, "_run_ffmpeg", AsyncMock(side_effect=fake_ffmpeg)) as ff,
    ):
        await execute.run(orch, "m.mkv")
    repair.assert_not_called()
    ff.assert_awaited_once()
    async with factory() as s:
        assert (await s.get(MediaItem, "m.mkv")).state == FileState.executed
    await engine.dispose()


async def test_convert_failure_keeps_ffmpeg_stderr(tmp_path):
    cfg, factory, engine = await _setup(tmp_path)
    orch = PipelineOrchestrator(factory, cfg)
    boom = subprocess.CalledProcessError(
        1, ["ffmpeg"], stderr="Invalid data found when processing input"
    )
    with patch("app.pipeline.types.video.convert_video", side_effect=boom):
        rc, err = await VideoStrategy.convert(
            orch,
            MediaItem(id="x", source_path="/in/x.avi"),
            Path("/in/x.avi"),
            tmp_path / "o.mkv",
        )
    assert rc == 1 and "Invalid data found" in err
    await engine.dispose()
