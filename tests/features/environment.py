import asyncio
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

# Must be set before anything imports app.core.database (behave loads the step
# modules, and that import binds the global engine to DATABASE_URL).
os.environ["DATABASE_URL"] = (
    f"sqlite+aiosqlite:///{tempfile.mkdtemp(prefix='mr-bdd-')}/bdd.sqlite"
)

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.models.saga  # noqa: F401 (import to register models with Base.metadata)
from app.models.media import Base


def before_all(context):
    """Create the schema in the temp-file DB selected at import time."""
    from app.core.database import init_db

    asyncio.run(init_db())


def before_scenario(context, scenario):
    """Prepare isolated test dirs and DB before each scenario."""
    # Setup temp dirs for input/staging/output
    context.tempdirs = {}
    for d in ["input", "staging", "output"]:
        tempdir = tempfile.TemporaryDirectory()
        context.tempdirs[d] = tempdir
        setattr(context, f"{d}_dir", tempdir.name)

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
    db_path = Path(os.environ["DATABASE_URL"].removeprefix("sqlite+aiosqlite:///"))

    # On failure, dump DB and copy ffmpeg logs into the scenario's temp output dir
    if scenario.status == "failed":
        if db_path.exists():
            dump_path = Path(context.output_dir) / "failure_db_dump.sql"
            with sqlite3.connect(str(db_path)) as conn, open(dump_path, "w") as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
        ffmpeg_log = Path("logs/ffmpeg.log")
        if ffmpeg_log.exists():
            shutil.copy(ffmpeg_log, Path(context.output_dir) / "ffmpeg_failure.log")

    # Dispose DB engine if the test created one
    engine = getattr(context, "engine", None)
    if engine is not None:
        try:  # noqa: SIM105
            asyncio.run(engine.dispose())
        except Exception:  # noqa: S110
            # Best-effort dispose; don't fail cleanup
            pass

    # Cleanup temp dirs
    for tempdir in getattr(context, "tempdirs", {}).values():
        try:  # noqa: SIM105
            tempdir.cleanup()
        except Exception:  # noqa: S110
            pass
