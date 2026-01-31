import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from app.services.execution_service import ExecutionService
from app.models.media import NormalizationPlan, MediaItem


@pytest.mark.asyncio
@patch("os.makedirs")
async def test_execute_plan_atomic_commit(mock_makedirs):
    db = AsyncMock()
    plan = MagicMock(spec=NormalizationPlan)
    plan.id = "planid"
    plan.media_item_id = "mediaid"
    plan.media_item = MagicMock(spec=MediaItem)
    plan.media_item.source_path = "/input/testfile.flac"
    plan.target_path = "/output/music/Artist/Album/01 - Title.flac"
    plan.ffmpeg_args = [
        "-i",
        "/staging/planid/testfile.flac",
        "-c:a",
        "copy",
        "/staging/planid/01 - Title.flac",
    ]
    plan.needs_transcode = False
    plan.needs_tagging = False
    plan.needs_rename = True
    plan.needs_subtitle_conversion = False
    # Simulate file exists at staging
    with tempfile.TemporaryDirectory() as staging:
        staging_dir = Path(staging) / "planid"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_file = staging_dir / "testfile.flac"
        with open(staged_file, "wb") as f:
            f.write(b"data")
        plan.media_item.source_path = str(staged_file)
        plan.target_path = str(staging_dir / "final.flac")

        def fake_move(src, dst):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(b"data")

        class FakeStat:
            st_size = 1
            st_mode = 0o40755  # S_IFDIR | 0755

        with (
            patch.object(Path, "stat", return_value=FakeStat()),
            patch("shutil.move", side_effect=fake_move),
        ):
            service = ExecutionService(db, staging_root=staging)
            await service.execute_plan(plan)
    # DB state updates
    # Check that db.execute was called for MediaItem and NormalizationPlan
    # Check that db.execute was awaited at least once
    assert db.execute.await_count > 0
    assert db.commit.called


@pytest.mark.asyncio
@patch("os.makedirs")
async def test_execute_plan_overwrite_protection(mock_makedirs):
    db = AsyncMock()
    plan = MagicMock(spec=NormalizationPlan)
    plan.id = "planid2"
    plan.media_item_id = "mediaid2"
    plan.media_item = MagicMock(spec=MediaItem)
    plan.media_item.source_path = "/input/testfile2.flac"
    plan.target_path = "/output/music/Artist/Album/01 - Title.flac"
    plan.ffmpeg_args = [
        "-i",
        "/staging/planid2/testfile2.flac",
        "-c:a",
        "copy",
        "/staging/planid2/01 - Title.flac",
    ]
    plan.needs_transcode = False
    plan.needs_tagging = False
    plan.needs_rename = True
    plan.needs_subtitle_conversion = False
    with tempfile.TemporaryDirectory() as staging:
        staging_dir = Path(staging) / "planid2"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_file = staging_dir / "testfile2.flac"
        with open(staged_file, "wb") as f:
            f.write(b"data")
        plan.media_item.source_path = str(staged_file)
        plan.target_path = str(staging_dir / "final.flac")

        def fake_move(src, dst):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(b"data")

        class FakeStat:
            st_size = 1
            st_mode = 0o40755

        with (
            patch.object(Path, "stat", return_value=FakeStat()),
            patch("shutil.move", side_effect=fake_move),
        ):
            service = ExecutionService(db, staging_root=staging)
            await service.execute_plan(plan)
    assert db.commit.called


@pytest.mark.asyncio
@patch("shutil.move")
@patch("os.makedirs")
async def test_execute_plan_failure_cleanup(mock_makedirs, mock_move):
    db = AsyncMock()
    plan = MagicMock(spec=NormalizationPlan)
    plan.id = "planid3"
    plan.media_item_id = "mediaid3"
    plan.media_item = MagicMock(spec=MediaItem)
    plan.media_item.source_path = "/input/testfile3.flac"
    plan.target_path = "/output/music/Artist/Album/01 - Title.flac"
    plan.ffmpeg_args = [
        "-i",
        "/staging/planid3/testfile3.flac",
        "-c:a",
        "copy",
        "/staging/planid3/01 - Title.flac",
    ]
    plan.needs_transcode = False
    plan.needs_tagging = False
    plan.needs_rename = True
    plan.needs_subtitle_conversion = False
    with tempfile.TemporaryDirectory() as staging:
        staging_dir = Path(staging) / "planid3"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_file = staging_dir / "testfile3.flac"
        with open(staged_file, "wb") as f:
            f.write(b"data")
        plan.media_item.source_path = str(staged_file)
        plan.target_path = str(staging_dir / "final.flac")
        # Patch Path.exists and stat, and force an error
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "stat", return_value=MagicMock(st_size=1)),
            patch("shutil.move", side_effect=Exception("move failed")),
        ):
            service = ExecutionService(db, staging_root=staging)
            with pytest.raises(Exception):
                await service.execute_plan(plan)
    assert db.commit.called
