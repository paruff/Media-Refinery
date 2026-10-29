"""#99 deferred music fidelity items, each pinned by a corpus case: nothing a user already
has (art, tags, bit depth) is silently lost, and a bad provider answer never auto-publishes."""

import hashlib
import io
import json
from pathlib import Path

import httpx
import pytest
from mutagen.flac import FLAC, Picture
from PIL import Image
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.core.tools import run_tool
from app.models.media import FileState, MediaItem
from app.services.music_id import MusicIdentifier
from tests.corpus.generate import tone
from tests.pipeline_helpers import import_input, make_config, make_session_factory
from tests.unit.test_music_id import RELEASE, identifier

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]

TAGS = {"artist": "Artist Z", "album": "Album Z", "date": "2020"}


def _jpeg(size: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), "red").save(buf, "JPEG")
    return buf.getvalue()


def _with_cover(path: Path, size: int) -> Path:
    audio = FLAC(path)
    pic = Picture()
    pic.type, pic.mime, pic.data = 3, "image/jpeg", _jpeg(size)
    audio.add_picture(pic)
    audio.save()
    return path


async def _run(tmp_path, *, ident=None, approve=True, **cfg_kw):
    cfg = make_config(tmp_path, enabled_types=frozenset({"music"}), **cfg_kw)
    engine, factory = await make_session_factory(tmp_path)
    return cfg, engine, factory, ident


async def _go(cfg, factory, ident=None, approve=True):
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg, identifier=ident)
    await orch.run_until_idle()
    if approve:
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
    async with factory() as s:
        return (await s.execute(select(MediaItem))).scalars().all()


async def _stream(path: Path) -> dict:
    _, out, _ = await run_tool(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_streams", "-of", "json", str(path)], 60
    )  # fmt: skip
    return json.loads(out)["streams"][0]


def _published(cfg, pattern="*.flac") -> list[Path]:
    return sorted(cfg.music_root.rglob(pattern))


async def test_small_embedded_cover_survives(tmp_path):
    """-map 0:a drops pictures; a cover below 500 px is still better than none."""
    cfg, engine, factory, _ = await _run(tmp_path)
    src = tone(cfg.input_dir / "A/01.flac", codec="flac", track="1", title="T", **TAGS)
    _with_cover(src, 300)
    await _go(cfg, factory)
    (out,) = _published(cfg)
    assert FLAC(out).pictures, "small embedded cover was dropped"
    assert (out.parent / "cover.jpg").is_file()
    await engine.dispose()


@pytest.mark.parametrize(
    ("codec", "extra", "bits"),
    [("pcm_f32le", (), 24), ("pcm_u8", (), 16), ("pcm_s24le", (), 24), ("pcm_s16le", (), 16)],
)  # fmt: skip
async def test_flac_is_16_or_24_bit(tmp_path, codec, extra, bits):
    """R-MUSIC-1: 32-bit float and 8-bit sources become 16/24-bit FLAC, never pass through."""
    cfg, engine, factory, _ = await _run(tmp_path)
    tone(
        cfg.input_dir / "A/01.wav",
        codec=codec,
        extra=extra,
        track="1",
        title="T",
        **TAGS,
    )
    await _go(cfg, factory)
    (out,) = _published(cfg)
    s = await _stream(out)
    assert s["codec_name"] == "flac"
    assert int(s["bits_per_raw_sample"]) == bits, s
    await engine.dispose()


async def test_16_bit_flac_is_copied_not_reencoded(tmp_path):
    cfg, engine, factory, _ = await _run(tmp_path)
    src = tone(cfg.input_dir / "A/01.flac", codec="flac", track="1", title="T", **TAGS)

    async def md5(p):
        _, o, _ = await run_tool(["ffmpeg", "-nostdin", "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5", "-"], 60)  # fmt: skip
        return o

    before = await md5(src)
    await _go(cfg, factory)
    (out,) = _published(cfg)
    assert await md5(out) == before
    await engine.dispose()


async def test_identified_tags_keep_full_date_and_every_artist(tmp_path):
    cfg, engine, factory, _ = await _run(tmp_path)
    tone(cfg.input_dir / "A/01.flac", codec="flac", **TAGS)
    await _go(cfg, factory, ident=identifier(), approve=True)
    (out,) = _published(cfg)
    tags = FLAC(out)
    assert tags["DATE"] == ["2021-05-01"]
    assert tags["MUSICBRAINZ_ARTISTID"] == ["a-9", "a-8"]
    await engine.dispose()


async def test_multidisc_track_without_number_has_no_bare_disc_prefix(tmp_path):
    cfg, engine, factory, _ = await _run(tmp_path)
    for disc in (1, 2):
        tone(cfg.input_dir / f"D{disc}/x.flac", codec="flac", freq=300 + disc, title="Song",
             disc=f"{disc}/2", **TAGS)  # fmt: skip
    await _go(cfg, factory)
    names = sorted(p.name for p in _published(cfg))
    assert len(names) == 2, names
    assert not any(n.startswith(("1-Song", "2-Song")) for n in names), names
    await engine.dispose()


async def test_stale_cover_jpg_is_replaced(tmp_path):
    cfg, engine, factory, _ = await _run(tmp_path)
    src = tone(cfg.input_dir / "A/01.flac", codec="flac", track="1", title="T", **TAGS)
    _with_cover(src, 600)
    stale = cfg.music_root / "Artist Z" / "Album Z (2020)" / "cover.jpg"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")
    await _go(cfg, factory)
    (out,) = _published(cfg)
    assert stale.read_bytes() == bytes(FLAC(out).pictures[0].data)
    await engine.dispose()


async def test_partial_mixed_format_album_publishes_the_good_tracks_only(tmp_path):
    cfg, engine, factory, _ = await _run(tmp_path)
    tone(cfg.input_dir / "A/01.mp3", freq=310, track="1", title="One", **TAGS)
    tone(
        cfg.input_dir / "A/02.flac",
        codec="flac",
        freq=320,
        track="2",
        title="Two",
        **TAGS,
    )
    (cfg.input_dir / "A/03.mp3").write_bytes(b"ID3\x04" + b"\x00" * 64)
    broken = (cfg.input_dir / "A/03.mp3").read_bytes()
    items = await _go(cfg, factory)
    out = {p.suffix for p in cfg.music_root.rglob("*") if p.suffix in (".mp3", ".flac")}
    assert out == {".mp3", ".flac"}
    bad = next(i for i in items if str(i.source_path).endswith("03.mp3"))
    assert bad.state in (FileState.error, FileState.quarantined)
    kept = [
        p
        for r in (cfg.input_dir, cfg.archive_dir, cfg.quarantine_dir)
        for p in r.rglob("03.mp3")
    ]
    assert any(hashlib.sha256(p.read_bytes()).digest() == hashlib.sha256(broken).digest() for p in kept)  # fmt: skip
    await engine.dispose()


@pytest.mark.parametrize("failure", ["low_score", "provider_503"])
async def test_auto_approve_never_publishes_a_doubtful_identification(
    tmp_path, failure
):
    cfg, engine, factory, _ = await _run(
        tmp_path, auto_approve_types=frozenset({"music"})
    )
    tone(cfg.input_dir / "A/01.flac", codec="flac", track="1", title="T", **TAGS)
    if failure == "low_score":
        ident = identifier(score=0.5)
    else:
        ident = MusicIdentifier(
            "key",
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(503))
            ),
            fingerprint=lambda p: (120, "fp"),
            mb_interval=0,
        )
    items = await _go(cfg, factory, ident=ident, approve=False)
    assert not _published(cfg), "auto-approve published an unconfirmed identification"
    assert [i.state for i in items] == [FileState.planned]
    await engine.dispose()


assert RELEASE  # shared fixture, imported for the identified-tags case
