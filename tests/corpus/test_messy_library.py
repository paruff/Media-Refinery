"""G15: the full pipeline over the generated messy library. Whatever the content, no source
is lost, nothing broken reaches the library, nothing crashes, and a rerun is a no-op."""

import hashlib
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.core.tools import run_tool
from app.models.media import FileState, MediaItem
from tests.corpus.generate import messy
from tests.pipeline_helpers import import_input, make_config, make_session_factory

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]


def _digests(root: Path) -> list[str]:
    return sorted(
        hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    )


async def test_messy_library_converges_without_loss_or_junk(tmp_path):
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    made = messy(cfg.input_dir)
    sources = _digests(cfg.input_dir)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    async with factory() as s:
        planned = (
            (
                await s.execute(
                    select(MediaItem.id).where(MediaItem.state == FileState.planned)
                )
            )
            .scalars()
            .all()
        )
    for item_id in planned:
        await orch.approve(str(item_id))
    await orch.run_until_idle()

    async with factory() as s:
        items = (await s.execute(select(MediaItem))).scalars().all()
    by_name = {Path(str(i.source_path)).name: i for i in items}
    # unreadable or non-media input may stop at `error` or go to quarantine, but must never
    # be processed further, and an `error` item's source stays where it was
    for i in items:
        if i.state == FileState.error:
            assert Path(str(i.source_path)).is_file(), i.source_path
    for kind in ("zero_byte", "garbage", "truncated"):
        for p in made[kind]:
            assert by_name[p.name].state in (FileState.error, FileState.quarantined), (
                p,
                by_name[p.name].state,
            )

    # nothing lost: every source byte-for-byte in input, archive or quarantine (quarantine
    # may also hold rejected outputs, so extras are fine; missing sources are not)
    kept = (
        _digests(cfg.input_dir)
        + _digests(cfg.archive_dir)
        + _digests(cfg.quarantine_dir)
    )
    assert not Counter(sources) - Counter(kept), "a source file was lost or modified"

    # nothing broken published: every library file decodes
    for f in [
        p
        for r in (cfg.music_root, cfg.movies_root)
        for p in r.rglob("*")
        if p.is_file()
    ]:
        if f.suffix in (".mp3", ".flac", ".mkv"):
            rc, _, err = await run_tool(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", str(f), "-f", "null", "-"],
                60,
            )
            assert rc == 0 and not err.strip(), (f, err)
    assert not list(cfg.music_root.rglob(".*.tmp"))

    # a rerun changes nothing
    before = _digests(cfg.music_root) + _digests(cfg.movies_root)
    await import_input(cfg, factory)
    await PipelineOrchestrator(factory, cfg).run_until_idle()
    assert _digests(cfg.music_root) + _digests(cfg.movies_root) == before
    await engine.dispose()


async def test_music_only_leaves_other_types_and_is_idempotent(tmp_path):
    """G16: ENABLED_TYPES={music} never touches the movie; re-ingesting the output tree
    (a moved/renamed copy of already-published files) adds nothing."""
    cfg = make_config(tmp_path, enabled_types=frozenset({"music"}))
    engine, factory = await make_session_factory(tmp_path)
    made = messy(cfg.input_dir)
    movie = made["movie"][0]
    movie_digest = hashlib.sha256(movie.read_bytes()).hexdigest()
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    async with factory() as s:
        for i in (
            await s.execute(
                select(MediaItem).where(MediaItem.state == FileState.planned)
            )
        ).scalars():
            await orch.approve(str(i.id))
    await orch.run_until_idle()

    assert (
        movie.is_file()
        and hashlib.sha256(movie.read_bytes()).hexdigest() == movie_digest
    )
    assert not any(cfg.movies_root.rglob("*.mkv"))
    out = _digests(cfg.music_root)
    assert out

    # feed the library back in as input: nothing new may be published
    import shutil

    shutil.copytree(cfg.music_root, cfg.input_dir / "reingest")
    await import_input(cfg, factory)
    await PipelineOrchestrator(factory, cfg).run_until_idle()
    assert _digests(cfg.music_root) == out
    await engine.dispose()


async def _audio_md5(path: Path) -> str:
    _, out, _ = await run_tool(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a", "-c", "copy", "-f", "md5", "-"],
        60,
    )  # fmt: skip
    return out.strip()


async def test_lossy_not_transcoded_and_tags_cover_replaygain_survive(tmp_path):
    """G16: a tagged mp3 with a cover is published with the identical audio stream, its
    tags and cover intact and ReplayGain added; ingesting the same file twice is a no-op."""
    import io
    import shutil

    from mutagen.id3 import APIC, ID3
    from mutagen.mp3 import MP3
    from PIL import Image

    from tests.corpus.generate import tone

    cfg = make_config(tmp_path, enabled_types=frozenset({"music"}))
    engine, factory = await make_session_factory(tmp_path)
    src = tone(
        cfg.input_dir / "Album/01.mp3", freq=350, artist="Artist Z", album="Album Z",
        title="Zed", track="1", date="2020",
    )  # fmt: skip
    buf = io.BytesIO()
    Image.new("RGB", (600, 600), "red").save(buf, "JPEG")
    tags = ID3(src)
    tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=buf.getvalue()))
    tags.save(src)
    audio_before = await _audio_md5(src)

    async def run():
        await import_input(cfg, factory)
        orch = PipelineOrchestrator(factory, cfg)
        await orch.run_until_idle()
        async with factory() as s:
            ids = (
                (
                    await s.execute(
                        select(MediaItem.id).where(MediaItem.state == FileState.planned)
                    )
                )
                .scalars()
                .all()
            )
        for i in ids:
            await orch.approve(str(i))
        await orch.run_until_idle()

    await run()
    out = list(cfg.music_root.rglob("*.mp3"))
    assert len(out) == 1, out
    pub = out[0]
    assert await _audio_md5(pub) == audio_before, "lossy audio was transcoded"
    f = MP3(pub)
    id3 = ID3(pub)
    assert str(id3["TPE1"]) == "Artist Z" and str(id3["TALB"]) == "Album Z"
    assert any(k.startswith("APIC") for k in id3), "cover lost"
    assert any("replaygain" in k.lower() for k in (f.tags.keys() if f.tags else [])), (
        list(f.tags or [])
    )

    # the same file dropped in again is a no-op
    before = _digests(cfg.music_root)
    shutil.copyfile(next(cfg.archive_dir.rglob("*.mp3")), cfg.input_dir / "again.mp3")
    await run()
    assert _digests(cfg.music_root) == before
    await engine.dispose()
