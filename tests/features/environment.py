import shutil
import sqlite3
from pathlib import Path
import tempfile
import asyncio


def before_scenario(context, scenario):
    """
    Reset the database and output directories before each scenario.
    """
    # Setup temp dirs
    context.tempdirs = {}
    for d in ["input", "staging", "output"]:
        tempdir = tempfile.TemporaryDirectory()
        context.tempdirs[d] = tempdir
        setattr(context, f"{d}_dir", tempdir.name)

    db_path = Path("data/media_refinery.sqlite")
    if db_path.exists():
        db_path.unlink()
    # Optionally, re-initialize DB schema if needed
    # os.system("alembic upgrade head")

    for d in ["output", "work"]:
        dir_path = Path(d)
        if dir_path.exists():
            shutil.rmtree(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)

    log_path = Path("logs")
    if log_path.exists():
        shutil.rmtree(log_path)
    log_path.mkdir(parents=True, exist_ok=True)
    if scenario.status == "failed":
        db_path = Path("data/media_refinery.sqlite")
        if db_path.exists():
            dump_path = Path("output/failure_db_dump.sql")
            with sqlite3.connect(str(db_path)) as conn, open(dump_path, "w") as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
        ffmpeg_log = Path("logs/ffmpeg.log")
        if ffmpeg_log.exists():
            shutil.copy(ffmpeg_log, "output/ffmpeg_failure.log")
    # Cleanup temp dirs
    for tempdir in getattr(context, "tempdirs", {}).values():
        tempdir.cleanup()
    # Optionally dispose DB engine if present
    if hasattr(context, "engine"):
        asyncio.run(context.engine.dispose())
        if db_path.exists():
            dump_path = Path("output/failure_db_dump.sql")
            with sqlite3.connect(str(db_path)) as conn, open(dump_path, "w") as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
        # Copy FFmpeg logs if present
        ffmpeg_log = Path("logs/ffmpeg.log")
        if ffmpeg_log.exists():
            shutil.copy(ffmpeg_log, "output/ffmpeg_failure.log")
    # Cleanup temp dirs
    for tempdir in context.tempdirs.values():
        tempdir.cleanup()
    # Dispose DB
    asyncio.run(context.engine.dispose())
