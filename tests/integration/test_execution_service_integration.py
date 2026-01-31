import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models.media import MediaItem, NormalizationPlan, PlanStatus, Base
from app.services.execution_service import ExecutionService


@pytest.mark.asyncio
async def test_execution_service_integration(tmp_path):
    # Setup DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # Create input file
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        input_file = input_dir / "song.flac"
        input_file.write_bytes(b"musicdata")
        # Create MediaItem and Plan
        item = MediaItem(
            id="mid1",
            source_path=str(input_file),
            media_type="music",
            state="planned",
        )
        session.add(item)
        await session.commit()
        # Use a writable staging dir under tmp_path
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        plan = NormalizationPlan(
            id="pid1",
            media_item_id="mid1",
            target_path=str(
                tmp_path / "output" / "Artist" / "Album" / "01 - Title.flac"
            ),
            ffmpeg_args=["-i", str(input_file), "-c:a", "copy", str(input_file)],
            plan_status=PlanStatus.draft,
            needs_transcode=False,
            needs_rename=True,
            needs_subtitle_conversion=False,
            needs_tagging=False,
            original_hash="abc",
        )
        # Patch os.makedirs and /staging path in ExecutionService to use tmp_path/staging
        import app.services.execution_service as exec_mod

        orig_makedirs = exec_mod.os.makedirs

        def fake_makedirs(path, exist_ok=False):
            from pathlib import Path

            Path(path).mkdir(parents=True, exist_ok=True)

        exec_mod.os.makedirs = fake_makedirs
        # Patch Path in ExecutionService to use temp staging dir
        orig_new = exec_mod.Path.__new__

        def path_new(cls, *args, **kwargs):
            if args and isinstance(args[0], str) and args[0].startswith("/staging/"):
                return tmp_path / args[0].replace("/staging/", "")
            return orig_new(cls, *args, **kwargs)

        exec_mod.Path.__new__ = path_new
        try:
            executor = ExecutionService(session)
            await executor.execute_plan(plan)
        finally:
            exec_mod.Path.__new__ = orig_new
            exec_mod.os.makedirs = orig_makedirs
            # Remove reference to orig_staging_dir, which may not be defined
        session.add(plan)
        await session.commit()
        # Run executor
        executor = ExecutionService(session)
        await executor.execute_plan(plan)
        # Check output
        out_file = tmp_path / "output" / "Artist" / "Album" / "01 - Title.flac"
        assert out_file.exists()
        assert out_file.stat().st_size > 0
        # Check DB state
        updated_item = await session.get(MediaItem, "mid1")
        assert updated_item.state == "executed"
        updated_plan = await session.get(NormalizationPlan, "pid1")
        assert updated_plan.plan_status == PlanStatus.completed
        assert "Moved to output" in updated_plan.execution_log
