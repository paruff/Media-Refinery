"""P2: the pipeline over a generated messy audiobook library with real ffmpeg. Whatever the
input, no source is lost, every book is one M4B with chapters, a late part or a gap goes to
review instead of becoming a second book, podcasts stay out, and re-ingest is a no-op."""

import hashlib
import json
import shutil
import subprocess
import zlib
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem, MediaType
from tests.pipeline_helpers import (
    import_input,
    make_config,
    make_session_factory,
)

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]
BOOKS = "Audiobooks"


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *args], check=True)


def tone(
    path: Path, seconds: int, rate: int = 44100, codec: str = "libmp3lame", **tags
):
    meta = [a for k, v in tags.items() for a in ("-metadata", f"{k}={v}")]
    ff(
        *("-f", "lavfi", "-i", f"sine=frequency={200 + zlib.crc32(str(path).encode()) % 600}:duration={seconds}:sample_rate={rate}"),
        *meta,
        *("-c:a", codec, str(path)),
    )  # fmt: skip
    return path


def spoken(path: Path, minutes: int, **tags) -> Path:
    """Audio with a 3 s silence every minute, so silencedetect finds chapters."""
    meta = [a for k, v in tags.items() for a in ("-metadata", f"{k}={v}")]
    ff(
        *("-f", "lavfi", "-i", f"sine=frequency=330:duration={minutes * 60}:sample_rate=22050"),
        *("-af", "volume=enable='lt(mod(t,60),57)':volume=1,volume=enable='gte(mod(t,60),57)':volume=0"),
        *meta,
        *("-c:a", "libmp3lame", "-b:a", "32k", "-ac", "1", str(path)),
    )  # fmt: skip
    return path


def make_m4b(path: Path, title: str, chapters: int = 2) -> Path:
    meta = path.with_suffix(".ffmeta")
    meta.write_text(
        ";FFMETADATA1\n"
        + "".join(
            f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={n * 2000}\nEND={n * 2000 + 2000}\ntitle=Part {n + 1}\n"
            for n in range(chapters)
        )
    )
    ff(
        *("-f", "lavfi", "-i", f"sine=frequency=440:duration={chapters * 2}"),
        *("-i", str(meta), "-map_metadata", "1", "-map_chapters", "1"),
        *("-metadata", f"album={title}", "-metadata", "artist=M4B Author"),
        *("-c:a", "aac", "-f", "ipod", str(path)),
    )  # fmt: skip
    meta.unlink()
    return path


def messy_audiobooks(root: Path) -> dict[str, list[Path]]:
    """Input tree below `root`; returns {book key: its files}."""
    a = root / "Audiobooks"
    out: dict[str, list[Path]] = {}

    def book(key: str, *paths: Path) -> None:
        out[key] = list(paths)

    d = a / "Multi File"
    d.mkdir(parents=True)
    book(
        "multi",
        *(
            tone(d / f"{n:02d}.mp3", 2, album="Multi File", artist="Ann Author")
            for n in (1, 2, 10)
        ),
    )
    d = a / "Mixed"
    d.mkdir()
    book("mixed", tone(d / "01.mp3", 2, 44100, album="Mixed", artist="Mia X"),
         tone(d / "02.m4a", 2, 22050, "aac", album="Mixed", artist="Mia X"))  # fmt: skip
    d = a / "Gappy"
    d.mkdir()
    book(
        "gaps",
        *(
            tone(d / f"{n:02d}.mp3", 2, album="Gappy", artist="Gus G")
            for n in (1, 2, 4)
        ),
    )
    d = a / "Late Part"
    d.mkdir()
    book(
        "late",
        *(
            tone(d / f"{n:02d}.mp3", 2, album="Late Part", artist="Lee L")
            for n in (1, 2)
        ),
    )
    d = a / "Author Folder" / "Book One"
    d.mkdir(parents=True)
    book("one", tone(d / "01.mp3", 2, album="Book One", artist="Pat P"))
    d = a / "Author Folder" / "Book Two"
    d.mkdir()
    book("two", tone(d / "01.mp3", 2, album="Book Two", artist="Pat P"))
    d = a / "M4B Input"
    d.mkdir()
    book("m4b", make_m4b(d / "book.m4b", "M4B Input"))
    d = a / "Cue Book"
    d.mkdir()
    cue = d / "book.cue"
    book("cue", tone(d / "book.mp3", 4, album="Cue Book", artist="Cy C"), cue)
    cue.write_text(
        'FILE "book.mp3" MP3\n  TRACK 01 AUDIO\n    TITLE "One"\n    INDEX 01 00:00:00\n'
        '  TRACK 02 AUDIO\n    TITLE "Two"\n    INDEX 01 00:02:00\n'
    )
    d = a / "Silent Chapters"
    d.mkdir()
    book("silence", spoken(d / "book.mp3", 4, album="Silent Chapters", artist="Sy S"))
    # a podcast: short, no audiobook folder or genre, so it must stay music
    d = root / "Podcasts" / "Show"
    d.mkdir(parents=True)
    book(
        "podcast", tone(d / "ep1.mp3", 2, album="Show", artist="Host", genre="Podcast")
    )
    # untagged long audio (>= 1 h, R-PIPE-4) is an audiobook by duration alone
    d = root / "Misc" / "Long"
    d.mkdir(parents=True)
    long = d / "long.mp3"
    ff(*("-f", "lavfi", "-i", "sine=frequency=200:duration=3700:sample_rate=8000"),
       *("-c:a", "libmp3lame", "-b:a", "16k", "-ac", "1", str(long)))  # fmt: skip
    book("long", long)
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


async def by_name(factory) -> dict[str, MediaItem]:
    async with factory() as s:
        return {
            f"{Path(str(i.source_path)).parent.name}/{Path(str(i.source_path)).name}": i
            for i in (await s.execute(select(MediaItem))).scalars()
        }


async def drive(orch, factory) -> None:
    await orch.run_until_idle()
    async with factory() as s:
        planned = (
            await s.execute(select(MediaItem.id).where(MediaItem.state == FileState.planned))
        ).scalars().all()  # fmt: skip
    for item_id in planned:
        await orch.approve(str(item_id))
    await orch.run_until_idle()


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_chapters", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return json.loads(out)


def m4bs(cfg) -> dict[str, Path]:
    return {p.stem: p for p in cfg.audiobooks_root.rglob("*.m4b")}


def held(cfg, digest: str) -> int:
    return sum(
        sha(p) == digest
        for root in (cfg.input_dir, cfg.archive_dir, cfg.quarantine_dir)
        if root.exists()
        for p in root.rglob("*")
        if p.is_file()
    )


async def test_messy_audiobook_library_converges_without_loss_or_junk(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    cfg = make_config(tmp_path, enabled_types=frozenset({"audiobook"}))
    engine, factory = await make_session_factory(tmp_path)
    made = messy_audiobooks(tmp_path / "pristine")
    sources = {p: sha(p) for files in made.values() for p in files}
    shutil.copytree(tmp_path / "pristine", cfg.input_dir, dirs_exist_ok=True)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await drive(orch, factory)

    items, books = await by_name(factory), m4bs(cfg)
    # no source is lost
    assert [p for p, d in sources.items() if held(cfg, d) < 1] == []
    # one M4B per book, never one per file; each has chapters and a plausible duration
    assert {
        "Multi File",
        "Mixed",
        "Book One",
        "Book Two",
        "M4B Input",
        "Cue Book",
        "Silent Chapters",
    } <= set(books), books
    info = {k: probe(v) for k, v in books.items()}
    assert len(info["Multi File"]["chapters"]) == 3
    assert abs(float(info["Multi File"]["format"]["duration"]) - 6) < 1
    assert (
        abs(float(info["Mixed"]["format"]["duration"]) - 4) < 1
    )  # mixed rates/codecs merged
    assert len(info["M4B Input"]["chapters"]) == 2
    assert len(info["Cue Book"]["chapters"]) == 2
    assert len(info["Silent Chapters"]["chapters"]) >= 2
    # a multi-book author folder is two books
    assert "Book One" in books and "Book Two" in books
    # a gap (1, 2, 4) is flagged for review; this test approves everything, a real run waits
    assert "missing_parts" in str(items["Gappy/01.mp3"].enrichment_data)
    # a podcast never classifies as an audiobook
    assert items["Show/ep1.mp3"].media_type != MediaType.audiobook
    # untagged long audio is an audiobook
    assert items["Long/long.mp3"].media_type == MediaType.audiobook
    assert "Long" in books

    # a late part is held, never a new book
    late = cfg.input_dir / "Audiobooks" / "Late Part"
    tone(late / "03.mp3", 2, album="Late Part", artist="Lee L")
    await import_input(cfg, factory)
    await drive(orch, factory)
    after = await by_name(factory)
    assert after["Late Part/03.mp3"].state == FileState.quarantined
    assert "late_part" in str(after["Late Part/03.mp3"].error_log)
    assert len(m4bs(cfg)) == len(books)

    # idempotence: the same files dropped again change nothing
    before = sorted(
        p.relative_to(cfg.audiobooks_root)
        for p in cfg.audiobooks_root.rglob("*")
        if p.is_file()
    )
    states = {k: v.state for k, v in after.items()}
    shutil.copytree(tmp_path / "pristine", cfg.input_dir, dirs_exist_ok=True)
    await import_input(cfg, factory)
    await drive(orch, factory)
    assert (
        sorted(
            p.relative_to(cfg.audiobooks_root)
            for p in cfg.audiobooks_root.rglob("*")
            if p.is_file()
        )
        == before
    )
    assert {k: v.state for k, v in (await by_name(factory)).items()} == states
    await engine.dispose()
