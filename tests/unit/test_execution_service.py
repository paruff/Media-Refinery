import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from app.services.execution_service import ExecutionService
from app.models.media import NormalizationPlan, MediaItem


@pytest.mark.asyncio
@pytest.mark.timeout(10)
@patch("asyncio.create_subprocess_exec")
@patch("os.makedirs")
async def test_execute_plan_atomic_commit(mock_makedirs, mock_subproc):
    # Mock subprocess to avoid real process hangs
    proc_mock = MagicMock()
    proc_mock.communicate = AsyncMock(return_value=(b"", b""))
    proc_mock.returncode = 0
    mock_subproc.return_value = proc_mock
    db = AsyncMock()

    def session_factory():
        class DummyContext:
            async def __aenter__(self):
                return db

            async def __aexit__(self, exc_type, exc, tb):
                pass

        return DummyContext()

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

        # Simulate file system state
        fs = set()
        fs.add(str(staged_file))

        def fake_move(src, dst):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(b"data")
            fs.add(dst)
            if src in fs:
                fs.remove(src)

        def exists_side_effect(self):
            return str(self) in fs

        class DirStat:
            st_size = 0
            st_mode = 0o40755  # Directory

        class FileStat:
            st_size = 1
            st_mode = 0o100644  # Regular file

        def stat_side_effect(self):
            if str(self) in fs and str(self).endswith("final.flac"):
                return FileStat()
            return DirStat()

        with (
            patch.object(Path, "exists", side_effect=exists_side_effect, autospec=True),
            patch.object(Path, "stat", side_effect=stat_side_effect, autospec=True),
            patch("shutil.move", side_effect=fake_move),
        ):
            service = ExecutionService(
                db, staging_root=staging, session_factory=session_factory
            )
            await service.execute_plan(plan)
    assert db.execute.await_count > 0
    assert db.commit.called


@pytest.mark.asyncio
@pytest.mark.timeout(10)
@patch("asyncio.create_subprocess_exec")
@patch("os.makedirs")
async def test_execute_plan_overwrite_protection(mock_makedirs, mock_subproc):
    proc_mock = MagicMock()
    proc_mock.communicate = AsyncMock(return_value=(b"", b""))
    proc_mock.returncode = 0
    mock_subproc.return_value = proc_mock
    db = AsyncMock()

    def session_factory():
        class DummyContext:
            async def __aenter__(self):
                return db

            async def __aexit__(self, exc_type, exc, tb):
                pass

        return DummyContext()

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

        fs = set()
        fs.add(str(staged_file))

        def fake_move(src, dst):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(b"data")
            fs.add(dst)
            if src in fs:
                fs.remove(src)

        def exists_side_effect(self):
            return str(self) in fs

        class DirStat:
            st_size = 0
            st_mode = 0o40755  # Directory

        class FileStat:
            st_size = 1
            st_mode = 0o100644  # Regular file

        def stat_side_effect(self):
            if str(self) in fs and str(self).endswith("final.flac"):
                return FileStat()
            return DirStat()

        with (
            patch.object(Path, "exists", side_effect=exists_side_effect, autospec=True),
            patch.object(Path, "stat", side_effect=stat_side_effect, autospec=True),
            patch("shutil.move", side_effect=fake_move),
        ):
            service = ExecutionService(
                db, staging_root=staging, session_factory=session_factory
            )
            await service.execute_plan(plan)
    assert db.commit.called


@pytest.mark.asyncio
@pytest.mark.timeout(10)
@patch("asyncio.create_subprocess_exec")
@patch("shutil.move")
@patch("os.makedirs")
async def test_execute_plan_failure_cleanup(mock_makedirs, mock_move, mock_subproc):
    proc_mock = MagicMock()
    proc_mock.communicate = AsyncMock(return_value=(b"", b""))
    proc_mock.returncode = 0
    mock_subproc.return_value = proc_mock
    db = AsyncMock()

    def session_factory():
        class DummyContext:
            async def __aenter__(self):
                return db

            async def __aexit__(self, exc_type, exc, tb):
                pass

        return DummyContext()

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
            service = ExecutionService(
                db, staging_root=staging, session_factory=session_factory
            )
            await service.execute_plan(plan)
    assert db.commit.called
