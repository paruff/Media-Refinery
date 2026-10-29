"""G6 review: album-level correctness (ReplayGain across restarts, one release per album, discs, flac -t)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core import verify
from app.core.orchestrator import PipelineOrchestrator
from app.core.planning import build_plan
from app.models.media import FileState, MediaItem, MediaType
from app.pipeline.types.music import MusicStrategy
from app.services.classification import parse_disc
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]
ROOTS = {"music": "/lib/Music", "movie": "/lib/Movies", "series": "/lib/TV"}


def music(id, state, folder="/in/Album", tags=None):
    return MediaItem(
        id=id,
        source_path=f"{folder}/{id}.flac",
        state=state,
        media_type=MediaType.music,
        audio_codec="flac",
        enrichment_data=json.dumps(
            {"music": {"tags": tags or {}, "needs_review": False, "score": 1}}
        ),
    )


async def _orch(tmp_path, *items):
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    async with factory() as s:
        s.add_all(items)
        await s.commit()
    return PipelineOrchestrator(factory, cfg), factory, engine


# ---- album ReplayGain survives restarts -----------------------------------
GAIN = {"replaygain_album_gain": "-7.00 dB", "replaygain_album_peak": "0.9"}


async def test_album_gain_is_reused_from_an_already_planned_sibling(tmp_path):
    orch, factory, engine = await _orch(
        tmp_path,
        music("a", FileState.planned, tags=GAIN),
        music("b", FileState.enriched),
    )
    measure = AsyncMock(return_value=("-3.00 dB", "0.5"))
    with patch("app.pipeline.types.music.measure", measure):
        async with factory() as s:
            b = await s.get(MediaItem, "b")
            meta = json.loads(b.enrichment_data)
            await MusicStrategy().replaygain(orch, s, b, meta)
    assert meta["music"]["tags"]["replaygain_album_gain"] == "-7.00 dB"
    assert measure.await_count == 1  # the track only; no album re-measure on a subset
    await engine.dispose()


async def test_published_siblings_from_an_earlier_import_are_not_reused(tmp_path):
    orch, factory, engine = await _orch(
        tmp_path,
        music("a", FileState.published, tags=GAIN),
        music("b", FileState.enriched),
    )
    measure = AsyncMock(return_value=("-3.00 dB", "0.5"))
    with patch("app.pipeline.types.music.measure", measure):
        async with factory() as s:
            b = await s.get(MediaItem, "b")
            meta = json.loads(b.enrichment_data)
            await MusicStrategy().replaygain(orch, s, b, meta)
    assert meta["music"]["tags"]["replaygain_album_gain"] == "-3.00 dB"
    await engine.dispose()


# ---- one release per album ------------------------------------------------
async def test_tracks_matched_to_different_releases_are_all_flagged(tmp_path):
    orch, factory, engine = await _orch(
        tmp_path,
        music("a", FileState.enriched, tags={"musicbrainz_albumid": "rel-1"}),
        music("b", FileState.enriched, tags={"musicbrainz_albumid": "rel-2"}),
        music(
            "c",
            FileState.enriched,
            folder="/in/Other",
            tags={"musicbrainz_albumid": "rel-9"},
        ),
    )
    async with factory() as s:
        await MusicStrategy.check_album_consistency(
            orch, s, await s.get(MediaItem, "a")
        )
        await s.commit()
        flags = {
            i: json.loads((await s.get(MediaItem, i)).enrichment_data).get("review")
            for i in "abc"
        }
    assert flags["a"] == flags["b"] == ["split_release"] and flags["c"] is None
    await engine.dispose()


async def test_consistent_release_is_not_flagged(tmp_path):
    orch, factory, engine = await _orch(
        tmp_path,
        music("a", FileState.enriched, tags={"musicbrainz_albumid": "rel-1"}),
        music("b", FileState.enriched, tags={"musicbrainz_albumid": "rel-1"}),
    )
    async with factory() as s:
        await MusicStrategy.check_album_consistency(
            orch, s, await s.get(MediaItem, "a")
        )
        assert "review" not in json.loads((await s.get(MediaItem, "b")).enrichment_data)
    await engine.dispose()


# ---- discs without identification ----------------------------------------
@pytest.mark.parametrize(
    "disc,total,expected",
    [
        ("2/3", None, (2, 3)),
        ("1", "2", (1, 2)),
        ("3", None, (3, None)),
        (None, None, (None, None)),
        ("x", None, (None, None)),
    ],
)
def test_parse_disc(disc, total, expected):
    assert parse_disc(disc, total) == expected


def test_unidentified_multi_disc_album_gets_disc_prefix_from_embedded_tags():
    meta = {
        "track_number": 1,
        "track_title": "Intro",
        "disc_number": 2,
        "disc_total": 2,
    }
    item = MediaItem(
        id="i", source_path="/in/x.flac", media_type=MediaType.music, audio_codec="flac",
        artist="A", album="B", enrichment_data=json.dumps(meta),
    )  # fmt: skip
    assert build_plan(item, ROOTS, []).target_path.endswith("/B/2-01 - Intro.flac")


def test_single_disc_has_no_prefix():
    meta = {
        "track_number": 1,
        "track_title": "Intro",
        "disc_number": 1,
        "disc_total": 1,
    }
    item = MediaItem(
        id="i", source_path="/in/x.flac", media_type=MediaType.music, audio_codec="flac",
        artist="A", album="B", enrichment_data=json.dumps(meta),
    )  # fmt: skip
    assert build_plan(item, ROOTS, []).target_path.endswith("/B/01 - Intro.flac")


# ---- flac -t is not optional ---------------------------------------------
async def test_missing_flac_binary_fails_verification_visibly():
    with patch("app.core.verify.shutil.which", return_value=None):
        check = await verify._flac_test("/x.flac")
    assert check.passed is False and "not installed" in check.detail


async def test_unidentified_music_is_filed_by_its_embedded_artist_and_album():
    """B7 trial: classification keeps artist/album in enrichment_data; enrich must use them."""
    item = MediaItem(
        id="x",
        source_path="/in/1975 ABBA/01.flac",
        state=FileState.scanned,
        media_type=MediaType.music,
        audio_codec="flac",
        enrichment_data=json.dumps(
            {
                "artist": "ABBA",
                "album": "ABBA",
                "album_artist": "ABBA",
                "track_title": "Mamma Mia",
                "track_number": 1,
            }
        ),
    )
    await MusicStrategy().enrich(type("O", (), {"identifier": None})(), item)
    plan = build_plan(item, ROOTS, [])
    assert plan.target_path.endswith("/Music/ABBA/ABBA/01 - Mamma Mia.flac")
