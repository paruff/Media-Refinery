import asyncio
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
import mutagen
from behave import given, then  # type: ignore[import-untyped]
from PIL import Image

from app.core.orchestrator import PipelineOrchestrator
from app.services.music_id import MusicIdentifier
from tests.pipeline_helpers import (
    import_input,
    make_config,
    make_flac,
    make_mp3,
    make_session_factory,
)

TRACKS = [
    ("a", "rec-1", "Track One"),
    ("b", "rec-2", "Track Two"),
    ("c", "rec-3", "Track Three"),
]
ARTIST = [{"name": "Test Artist", "artist": {"id": "artist-1"}}]
R_MUSIC_2 = [
    "ARTIST",
    "ALBUMARTIST",
    "ALBUM",
    "TITLE",
    "TRACKNUMBER",
    "TRACKTOTAL",
    "DISCNUMBER",
    "DISCTOTAL",
    "DATE",
    "GENRE",
    "MUSICBRAINZ_TRACKID",
    "MUSICBRAINZ_ALBUMID",
    "MUSICBRAINZ_ARTISTID",
    "MUSICBRAINZ_ALBUMARTISTID",
    "REPLAYGAIN_TRACK_GAIN",
    "REPLAYGAIN_TRACK_PEAK",
    "REPLAYGAIN_ALBUM_GAIN",
    "REPLAYGAIN_ALBUM_PEAK",
]
ID3_FRAMES = {
    "ARTIST": "TPE1",
    "ALBUMARTIST": "TPE2",
    "ALBUM": "TALB",
    "TITLE": "TIT2",
    "DATE": "TDRC",
    "GENRE": "TCON",
}


def png(size: int = 600) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), "blue").save(buf, "PNG")
    return buf.getvalue()


def release(discs: int) -> dict:
    """MusicBrainz release JSON: one medium of three tracks, or 2 + 1 over two discs."""
    layout = [TRACKS] if discs == 1 else [TRACKS[:2], TRACKS[2:]]
    media = [
        {
            "position": n,
            "track-count": len(tracks),
            "tracks": [
                {"position": i, "title": title, "recording": {"id": rec}}
                for i, (_, rec, title) in enumerate(tracks, 1)
            ],
        }
        for n, tracks in enumerate(layout, 1)
    ]
    return {
        "id": "rel-1",
        "title": "Test Album",
        "date": "2021-05-01",
        "artist-credit": ARTIST,
        "genres": [{"name": "indie", "count": 3}],
        "media": media,
    }


def _handler(context):
    def handle(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "api.acoustid.org":
            stem = request.url.params["fingerprint"].removeprefix("fp-")
            rec = next(r for s, r, _ in TRACKS if s == stem)
            recording = {"id": rec, "releases": [{"id": "rel-1"}]}
            body = {"results": [{"score": context.score, "recordings": [recording]}]}
            return httpx.Response(200, json=body)
        if path.endswith("/release/rel-1") and host == "musicbrainz.org":
            return httpx.Response(200, json=release(context.discs))
        if host == "coverartarchive.org":
            return httpx.Response(200, content=png())
        return httpx.Response(404)

    return handle


def _run(context, coro):
    return context.spine_loop.run_until_complete(coro)


@given("a music workspace with mocked AcoustID, MusicBrainz and Cover Art Archive")
def step_workspace(context):
    if not shutil.which("ffmpeg"):
        context.scenario.skip("ffmpeg not installed (see `make docker-test`)")
        return
    tmp = tempfile.TemporaryDirectory()
    context.add_cleanup(tmp.cleanup)
    base = Path(tmp.name)
    context.score, context.discs = 0.97, 1
    context.spine_loop = asyncio.new_event_loop()
    context.add_cleanup(context.spine_loop.close)
    context.cfg = make_config(base, auto_approve_types=frozenset({"music"}))
    engine, context.factory = _run(context, make_session_factory(base))
    context.add_cleanup(lambda: _run(context, engine.dispose()))
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(_handler(context)), follow_redirects=True
    )
    identifier = MusicIdentifier(
        "k",
        client=client,
        fingerprint=lambda path: (2, f"fp-{Path(path).stem}"),
        mb_interval=0,
    )
    context.orch = PipelineOrchestrator(
        context.factory, context.cfg, identifier=identifier
    )


def _album(context, ext, make):
    for n, (stem, _, _) in enumerate(TRACKS):
        # distinct audio per track, or duplicate detection skips the later ones
        make(context.cfg.input_dir / f"{stem}.{ext}", seconds=2 + n, freq=330 + 110 * n)
    _run(context, import_input(context.cfg, context.factory))


@given("a generated FLAC album of 3 tracks")
def step_flac_album(context):
    _album(context, "flac", make_flac)


@given("a generated FLAC album of 3 tracks on 2 discs")
def step_two_discs(context):
    context.discs = 2
    _album(context, "flac", make_flac)


@given("a generated MP3 album of 3 tracks")
def step_mp3_album(context):
    _album(context, "mp3", make_mp3)


@given("AcoustID answers with a score of {score:f}")
def step_score(context, score):
    context.score = score


def _tracks(context) -> list[Path]:
    return sorted(
        p for p in context.cfg.music_root.rglob("*") if p.suffix in (".flac", ".mp3")
    )


def _tags(path: Path) -> dict[str, str]:
    """Tags under their Vorbis names, whatever the container."""
    audio = mutagen.File(path)
    if hasattr(audio, "pictures"):  # FLAC: Vorbis comments
        return {k.upper(): v[0] for k, v in audio.tags.items()}
    tags = {
        name: str(audio.tags[frame])
        for name, frame in ID3_FRAMES.items()
        if frame in audio.tags
    }
    for frame in audio.tags.getall("TXXX"):
        tags[frame.desc.upper()] = str(frame.text[0])
    for name, frame in (("TRACK", "TRCK"), ("DISC", "TPOS")):
        number, _, total = str(audio.tags[frame]).partition("/")
        tags[f"{name}NUMBER"], tags[f"{name}TOTAL"] = number, total
    return tags


@then('the album is published in "{folder}" as:')
def step_published(context, folder):
    album = context.cfg.music_root / folder
    got = sorted(p.name for p in album.glob("*") if p.suffix in (".flac", ".mp3"))
    assert got == sorted(r["file"] for r in context.table), (
        got,
        sorted(str(p) for p in context.cfg.music_root.rglob("*")),
    )


@then("every published track carries all R-MUSIC-2 tags")
def step_tags(context):
    tracks = _tracks(context)
    assert len(tracks) == 3, tracks
    for path in tracks:
        tags = _tags(path)
        missing = [k for k in R_MUSIC_2 if not tags.get(k)]
        assert not missing, (path.name, missing, tags)
        assert tags["ALBUM"] == "Test Album" and tags["ALBUMARTIST"] == "Test Artist"
        assert tags["DATE"] == "2021-05-01" and tags["GENRE"] == "indie"
        assert tags["MUSICBRAINZ_ALBUMID"] == "rel-1"
        assert tags["MUSICBRAINZ_ALBUMARTISTID"] == "artist-1"
        assert tags["REPLAYGAIN_TRACK_GAIN"].endswith(" dB")
    assert (
        len({_tags(p)["REPLAYGAIN_ALBUM_GAIN"] for p in tracks}) == 1
    )  # one per album


def _assert_cover(data: bytes):
    img = Image.open(io.BytesIO(data))
    assert (
        img.format == "JPEG" and min(img.size) >= 500 and len(data) <= 2 * 1024 * 1024
    )


@then("every published track embeds a front cover of at least 500 px")
def step_cover(context):
    for path in _tracks(context):
        audio = mutagen.File(path)
        pictures = audio.pictures
        assert [p.type for p in pictures] == [3], path
        _assert_cover(pictures[0].data)


@then("the album folder holds cover.jpg")
def step_cover_jpg(context):
    covers = list(context.cfg.music_root.rglob("cover.jpg"))
    assert len(covers) == 1, covers
    _assert_cover(covers[0].read_bytes())


@then("flac verifies every published track")
def step_flac_t(context):
    for path in _tracks(context):
        subprocess.run(["flac", "-t", "-s", str(path)], check=True)


@then('every published track is still "{codec}"')
def step_codec(context, codec):
    for path in _tracks(context):
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert out == codec, (path, out)


@then("nothing is published")
def step_nothing_published(context):
    assert not [p for p in context.cfg.music_root.rglob("*") if p.is_file()]


@then("{count:d} tracks are published")
def step_count_published(context, count):
    assert len(_tracks(context)) == count, _tracks(context)
