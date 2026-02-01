import shutil
import sqlite3
from pathlib import Path
import tempfile
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import Base


def before_scenario(context, scenario):
    """Prepare isolated test dirs and DB before each scenario."""
    # Setup temp dirs for input/staging/output
    context.tempdirs = {}
    for d in ["input", "staging", "output"]:
        tempdir = tempfile.TemporaryDirectory()
        context.tempdirs[d] = tempdir
        setattr(context, f"{d}_dir", tempdir.name)

    # Ensure working directories exist
    for d in ["output", "work", "logs", "data"]:
        dir_path = Path(d)
        if dir_path.exists():
            shutil.rmtree(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)

    # Remove any previous sqlite DB to start clean
    db_path = Path("data/media_refinery.sqlite")
    if db_path.exists():
        db_path.unlink()

    # Setup an in-memory async DB engine and create tables
    context.engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    context.AsyncSessionLocal = sessionmaker(
        context.engine, expire_on_commit=False, class_=AsyncSession
    )

    async def _create_all():
        async with context.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_all())

    # Provide a callable async session factory to steps (use as `async with context.db()`)
    context.db = context.AsyncSessionLocal


def after_scenario(context, scenario):
    """Cleanup after each scenario and dump artifacts on failure."""
    db_path = Path("data/media_refinery.sqlite")

    # On failure, dump DB and copy ffmpeg logs for debugging
    if scenario.status == "failed":
        if db_path.exists():
            dump_path = Path("output/failure_db_dump.sql")
            with sqlite3.connect(str(db_path)) as conn, open(dump_path, "w") as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
        ffmpeg_log = Path("logs/ffmpeg.log")
        if ffmpeg_log.exists():
            shutil.copy(ffmpeg_log, "output/ffmpeg_failure.log")

    # Dispose DB engine if the test created one
    engine = getattr(context, "engine", None)
    if engine is not None:
        try:
            asyncio.run(engine.dispose())
        except Exception:
            # Best-effort dispose; don't fail cleanup
            pass

    # Cleanup temp dirs
    for tempdir in getattr(context, "tempdirs", {}).values():
        try:
            tempdir.cleanup()
        except Exception:
            pass
