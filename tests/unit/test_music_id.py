import io

import httpx
import pytest
from PIL import Image

from app.services import music_id
from app.services.music_id import (
    MAX_CACHED_RELEASES,
    MusicIdentifier,
    ProviderUnavailable,
    jpeg_cover,
    write_album_cover,
)

RELEASE = {
    "id": "rel-1",
    "title": "Test Album",
    "date": "2021-05-01",
    "artist-credit": [{"name": "Test Artist", "artist": {"id": "art-1"}}],
    "genres": [{"name": "rock", "count": 1}, {"name": "indie", "count": 5}],
    "media": [
        {
            "position": 1,
            "track-count": 2,
            "tracks": [
                {
                    "position": 1,
                    "title": "One",
                    "recording": {"id": "rec-1"},
                    "artist-credit": [
                        {"name": "Feat", "joinphrase": " & ", "artist": {"id": "a-9"}},
                        {"name": "Guest", "artist": {"id": "a-8"}},
                    ],
                },
                {"position": 2, "title": "Two", "recording": {"id": "rec-2"}},
            ],
        },
        {"position": 2, "track-count": 1, "tracks": []},
    ],
}


def png(size: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), "red").save(buf, "PNG")
    return buf.getvalue()


def identifier(score=0.97, calls=None, releases=True):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.host)
        if request.url.host == "api.acoustid.org":
            rec = {"id": "rec-1", "releases": [{"id": "rel-1"}] if releases else []}
            return httpx.Response(
                200, json={"results": [{"score": score, "recordings": [rec]}]}
            )
        if request.url.path.endswith("/release/rel-1"):
            return httpx.Response(200, json=RELEASE)
        if request.url.host == "coverartarchive.org":
            return httpx.Response(200, content=png(600))
        return httpx.Response(404)

    return MusicIdentifier(
        "key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        fingerprint=lambda path: (120, "fp"),
        mb_interval=0,
    )


@pytest.mark.asyncio
async def test_identify_maps_release_to_r_music_2_tags():
    score, tags = await identifier().identify("a.flac")
    assert score == 0.97
    assert tags == {
        "artist": "Feat & Guest",
        "album_artist": "Test Artist",
        "album": "Test Album",
        "title": "One",
        "track_number": 1,
        "track_total": 2,
        "disc_number": 1,
        "disc_total": 2,
        "year": "2021",
        "release_date": "2021-05-01",
        "genre": "indie",
        "musicbrainz_trackid": "rec-1",
        "musicbrainz_albumid": "rel-1",
        "musicbrainz_artistid": ["a-9", "a-8"],
        "musicbrainz_albumartistid": ["art-1"],
    }


@pytest.mark.asyncio
async def test_release_is_fetched_once_per_album():
    calls: list[str] = []
    ident = identifier(calls=calls)
    await ident.identify("a.flac")
    await ident.identify("b.flac")
    assert calls.count("musicbrainz.org") == 1


@pytest.mark.parametrize("releases", [False])
@pytest.mark.asyncio
async def test_no_release_is_no_match(releases):
    assert await identifier(releases=releases).identify("a.flac") is None


@pytest.mark.asyncio
async def test_no_fingerprint_is_no_match():
    ident = identifier()
    ident._fingerprint = lambda path: None
    assert await ident.identify("a.flac") is None


@pytest.mark.asyncio
async def test_cover_art_archive_fallback_is_jpeg_at_least_500px():
    data = await identifier().cover("missing.flac", "rel-1")
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG" and min(img.size) >= 500


def test_jpeg_cover_rejects_small_images():
    assert jpeg_cover(png(499)) is None
    assert jpeg_cover(b"not an image") is None


def test_jpeg_cover_shrinks_to_2mb():
    noise = Image.frombytes(
        "RGB", (2400, 2400), __import__("os").urandom(2400 * 2400 * 3)
    )
    buf = io.BytesIO()
    noise.save(buf, "PNG")
    out = jpeg_cover(buf.getvalue())
    assert out is not None and len(out) <= 2 * 1024 * 1024


@pytest.mark.asyncio
async def test_flac_test_failure_fails_verify(monkeypatch, tmp_path):
    from app.core import verify

    calls = []

    async def fake(args, limit=0):
        calls.append(args[0])
        return (
            (1, "", "FLAC__STREAM_DECODER_ERROR") if args[0] == "flac" else (0, "", "")
        )

    async def dur(path, limit=120):
        return 2.0

    monkeypatch.setattr(verify, "run_tool", fake)
    monkeypatch.setattr(verify, "probe_duration", dur)
    monkeypatch.setattr(verify.shutil, "which", lambda name: "/usr/bin/flac")
    out = tmp_path / "x.flac"
    out.write_bytes(b"x")
    _, _, reason = await verify.verify_output(str(out), str(out), True)
    assert reason == "flac_test_failed" and "flac" in calls


@pytest.mark.asyncio
async def test_musicbrainz_requests_are_spaced_by_the_interval():
    sleeps: list[float] = []

    async def sleep(s):
        sleeps.append(s)

    ident = identifier()
    ident._sleep = ident._mb_pace._sleep = sleep
    ident._mb_pace.interval = (
        1000.0  # any gap is far below this, whatever the wall clock
    )
    await ident._release("rel-1")
    ident._releases.clear()
    await ident._release("rel-1")
    assert len(sleeps) == 1 and 900 < sleeps[0] <= 1000


def flaky(statuses, calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "api.acoustid.org":
            rec = {"id": "rec-1", "releases": [{"id": "rel-1"}]}
            return httpx.Response(
                200, json={"results": [{"score": 0.97, "recordings": [rec]}]}
            )
        status = statuses.pop(0) if statuses else 200
        return (
            httpx.Response(200, json=RELEASE)
            if status == 200
            else httpx.Response(status, headers={"Retry-After": "0"})
        )

    sleeps: list[float] = []

    async def sleep(s):
        sleeps.append(s)

    ident = MusicIdentifier(
        "key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        fingerprint=lambda p: (120, "fp"),
        mb_interval=0,
        sleep=sleep,
    )
    return ident, sleeps


@pytest.mark.asyncio
async def test_musicbrainz_429_is_retried_then_succeeds():
    calls: list[str] = []
    ident, _ = flaky([429, 503], calls)
    assert (await ident.identify("a.flac"))[1]["album"] == "Test Album"
    assert calls.count("musicbrainz.org") == 3


@pytest.mark.asyncio
async def test_persistent_rate_limit_is_not_a_no_match():
    ident, _ = flaky([429, 429, 429], [])
    with pytest.raises(ProviderUnavailable):
        await ident.identify("a.flac")


@pytest.mark.asyncio
async def test_acoustid_requests_are_paced_to_three_per_second():
    ident, sleeps = flaky([], [])
    await ident.identify("a.flac")
    await ident.identify("b.flac")
    assert any(0 < s <= 1 / 3 for s in sleeps)


@pytest.mark.asyncio
async def test_release_cache_is_bounded():
    ident = identifier()
    ident._releases.update({str(n): {} for n in range(MAX_CACHED_RELEASES)})
    await ident._release("rel-1")
    assert len(ident._releases) == MAX_CACHED_RELEASES and "0" not in ident._releases


def _track_with_cover(monkeypatch, tmp_path, size, fmt="JPEG"):
    buf = io.BytesIO()
    Image.new("RGB", (size, size), "blue").save(buf, fmt)
    monkeypatch.setattr(music_id, "embedded_cover", lambda p: buf.getvalue())
    return tmp_path / "t.flac"


def test_smaller_cover_does_not_replace_a_larger_one(monkeypatch, tmp_path):
    big = tmp_path / "cover.jpg"
    Image.new("RGB", (900, 900)).save(big, "JPEG")
    before = big.read_bytes()
    assert write_album_cover(_track_with_cover(monkeypatch, tmp_path, 600))
    assert big.read_bytes() == before


def test_undecodable_existing_cover_is_replaced_and_png_becomes_jpeg(
    monkeypatch, tmp_path
):
    (tmp_path / "cover.jpg").write_bytes(b"junk")
    assert write_album_cover(_track_with_cover(monkeypatch, tmp_path, 600, "PNG"))
    assert Image.open(tmp_path / "cover.jpg").format == "JPEG"
