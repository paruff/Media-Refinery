import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import MediaItem, NormalizationPlan, PlanStatus, Base
from app.services.execution_service import ExecutionService


@pytest.mark.asyncio
async def test_ffmpeg_transcoding_integration(monkeypatch, tmp_path):
    # Setup DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # Create input file
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        input_file = input_dir / "movie.mkv"
        input_file.write_bytes(b"movie")
        # Create MediaItem and Plan
        item = MediaItem(
            id="midint",
            source_path=str(input_file),
            media_type="video",
            state="planned",
        )
        session.add(item)
        await session.commit()
        plan = NormalizationPlan(
            id="pidint",
            media_item_id="midint",
            target_path=str(tmp_path / "output" / "movie.mkv"),
            ffmpeg_args=[],
            plan_status=PlanStatus.draft,
            needs_transcode=True,
            needs_rename=True,
            needs_subtitle_conversion=False,
            needs_tagging=False,
            original_hash="abc",
        )
        session.add(plan)
        await session.commit()

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

        import shutil

        monkeypatch.setattr(shutil, "move", fake_move)
        executor = ExecutionService(session, staging_root=tmp_path)
        await executor.execute_plan(plan)
        # Check output
        out_file = tmp_path / "output" / "movie.mkv"
        assert out_file.exists()
        assert out_file.stat().st_size > 0
        # Check DB state
        updated_item = await session.get(MediaItem, "midint")
        assert updated_item.state == "executed"
        updated_plan = await session.get(NormalizationPlan, "pidint")
        assert updated_plan.plan_status == PlanStatus.completed.value
        assert "Moved to output" in updated_plan.execution_log
