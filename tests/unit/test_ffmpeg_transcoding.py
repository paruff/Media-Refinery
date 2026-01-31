import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from app.services.execution_service import ExecutionService
from app.models.media import NormalizationPlan, MediaItem


@pytest.mark.asyncio
def test_execute_plan_transcode_4k(monkeypatch):
    db = AsyncMock()
    plan = MagicMock(spec=NormalizationPlan)
    plan.id = "planid4k"
    plan.media_item_id = "mediaid4k"
    plan.media_item = MagicMock(spec=MediaItem)
    plan.media_item.source_path = "/input/testfile4k.mkv"
    plan.target_path = "/output/4k/final.mkv"
    plan.needs_transcode = True
    plan.surround = False
    plan.needs_tagging = False
    with tempfile.TemporaryDirectory() as staging:
        staging_dir = Path(staging) / "planid4k"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_file = staging_dir / "testfile4k.mkv"
        with open(staged_file, "wb") as f:
            f.write(b"data")
        plan.media_item.source_path = str(staged_file)
        plan.target_path = str(staging_dir / "final.mkv")

        # Patch ffprobe and ffmpeg subprocesses
        async def fake_create_subprocess_exec(*args, **kwargs):
            class Proc:
                def __init__(self, args):
                    self.args = args
                    self.returncode = 0

                async def communicate(self):
                    if "ffprobe" in self.args[0]:
                        if "stream=width,height" in self.args:
                            return (b"3840,2160", b"")  # 4K
                        if "stream=codec_name" in self.args:
                            return (b"hevc", b"")
                    if "ffmpeg" in self.args[0]:
                        return (b"ffmpeg ok", b"")
                    return (b"", b"")

            return Proc(args)

        monkeypatch.setattr(
            "asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )

        # Patch shutil.move to simulate file move
        def fake_move(src, dst):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(b"data")

        import app.services.execution_service as exec_mod

        orig_new = exec_mod.Path.__new__

        def path_new(cls, *args, **kwargs):
            if args and isinstance(args[0], str) and args[0].startswith("/staging/"):
                return Path(staging) / args[0].replace("/staging/", "")
            return orig_new(cls, *args, **kwargs)

        exec_mod.Path.__new__ = path_new
        try:
            with patch("shutil.move", side_effect=fake_move):
                service = ExecutionService(db)
                import asyncio

                asyncio.run(service.execute_plan(plan))
        finally:
            exec_mod.Path.__new__ = orig_new
    assert db.execute.await_count > 0
    assert db.commit.await_count > 0


@pytest.mark.asyncio
def test_execute_plan_transcode_1080p(monkeypatch):
    db = AsyncMock()
    plan = MagicMock(spec=NormalizationPlan)
    plan.id = "planid1080"
    plan.media_item_id = "mediaid1080"
    plan.media_item = MagicMock(spec=MediaItem)
    plan.media_item.source_path = "/input/testfile1080.mkv"
    plan.target_path = "/output/1080p/final.mkv"
    plan.needs_transcode = True
    plan.surround = True
    plan.needs_tagging = False
    with tempfile.TemporaryDirectory() as staging:
        staging_dir = Path(staging) / "planid1080"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_file = staging_dir / "testfile1080.mkv"
        with open(staged_file, "wb") as f:
            f.write(b"data")
        plan.media_item.source_path = str(staged_file)
        plan.target_path = str(staging_dir / "final.mkv")

        # Patch ffprobe and ffmpeg subprocesses
        async def fake_create_subprocess_exec(*args, **kwargs):
            class Proc:
                def __init__(self, args):
                    self.args = args
                    self.returncode = 0

                async def communicate(self):
                    if "ffprobe" in self.args[0]:
                        if "stream=width,height" in self.args:
                            return (b"1920,1080", b"")  # 1080p
                        if "stream=codec_name" in self.args:
                            return (b"h264", b"")
                    if "ffmpeg" in self.args[0]:
                        return (b"ffmpeg ok", b"")
                    return (b"", b"")

            return Proc(args)

        monkeypatch.setattr(
            "asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )

        # Patch shutil.move to simulate file move
        def fake_move(src, dst):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(b"data")
            import app.services.execution_service as exec_mod

            orig_new = exec_mod.Path.__new__

            def path_new(cls, *args, **kwargs):
                if (
                    args
                    and isinstance(args[0], str)
                    and args[0].startswith("/staging/")
                ):
                    return Path(staging) / args[0].replace("/staging/", "")
                return orig_new(cls, *args, **kwargs)

            exec_mod.Path.__new__ = path_new
            try:
                with patch("shutil.move", side_effect=fake_move):
                    service = ExecutionService(db)
                    import asyncio

                    asyncio.run(service.execute_plan(plan))
            finally:
                exec_mod.Path.__new__ = orig_new

    assert db.execute.await_count > 0
    assert db.commit.await_count > 0
