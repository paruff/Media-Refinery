"""Shared fixtures for the pipeline-spine integration tests and behave steps."""

import hashlib
import subprocess
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.models.saga  # noqa: F401 (registers the saga table)
from app.core.orchestrator import PipelineConfig
from app.models.media import Base


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *args], check=True)


def make_mp3(path: Path, seconds: int = 2, **tags: str) -> Path:
    meta = [a for k, v in tags.items() for a in ("-metadata", f"{k}={v}")]
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={seconds}",
        *meta,
        "-c:a",
        "libmp3lame",
        str(path),
    )
    return path


def make_mkv(path: Path, seconds: int = 2) -> Path:
    """Conformant H.264/AAC MKV (remuxed, not re-encoded)."""
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size=160x120:rate=10:duration={seconds}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=330:duration={seconds}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(path),
    )
    return path


def make_avi(path: Path, seconds: int = 2) -> Path:
    """MPEG-4 part 2 / MP3 AVI: not conformant, forces a re-encode to H.264."""
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size=160x120:rate=10:duration={seconds}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=330:duration={seconds}",
        "-c:v",
        "mpeg4",
        "-c:a",
        "libmp3lame",
        "-shortest",
        str(path),
    )
    return path


def tree_digest(*roots: Path) -> dict[str, str]:
    """{relative path: sha256} for every file (and empty marker for dirs) under roots."""
    out: dict[str, str] = {}
    for root in roots:
        for p in sorted(root.rglob("*")):
            key = str(p)
            out[key] = (
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<dir>"
            )
    return out


def make_config(base: Path, **overrides) -> PipelineConfig:
    cfg = PipelineConfig(
        input_dir=base / "input",
        work_dir=base / "work",
        archive_dir=base / "archive",
        quarantine_dir=base / "quarantine",
        music_root=base / "lib" / "Music",
        movies_root=base / "lib" / "Movies",
        tv_root=base / "lib" / "TV",
        **overrides,
    )
    for d in (cfg.input_dir, cfg.music_root, cfg.movies_root, cfg.tv_root):
        d.mkdir(parents=True, exist_ok=True)
    return cfg


async def make_session_factory(base: Path):
    """Fresh file DB per scenario (concurrent sessions need a real file, not :memory:)."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{base / 'pipeline.sqlite'}", future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def import_input(cfg: PipelineConfig, session_factory) -> list[str]:
    """What the watcher does after the stability window: one pending item per file."""
    from app.core.watcher import InputWatcher

    watcher = InputWatcher.__new__(InputWatcher)
    import logging

    watcher.db_session_factory = session_factory
    watcher.logger = logging.getLogger("test")
    watcher.coordinator = None
    ids = []
    for p in sorted(cfg.input_dir.rglob("*")):
        if p.is_file():
            await watcher.insert_if_new(str(p))
    from sqlalchemy import select

    from app.models.media import MediaItem

    async with session_factory() as s:
        ids = list((await s.execute(select(MediaItem.id))).scalars())
    return ids
