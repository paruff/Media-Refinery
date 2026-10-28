import asyncio

import httpx

from app.core.planning import build_plan, video_conformant
from app.models.media import MediaItem, MediaType
from app.services.enrich import VideoEnricher

ROOTS = {"music": "/lib/Music", "movie": "/lib/Movies", "series": "/lib/TV"}


def _v(codec="h264", profile="High", level=41):
    return {
        "codec_type": "video",
        "codec_name": codec,
        "profile": profile,
        "level": level,
    }


def _a(codec, channels):
    return {"codec_type": "audio", "codec_name": codec, "channels": channels}


def _movie(**kw):
    return MediaItem(
        id="i",
        source_path="/in/x.mkv",
        media_type=MediaType.movie,
        video_codec="h264",
        **kw,
    )


def test_conformance_rules():
    assert video_conformant(_v())
    assert not video_conformant(_v(level=51))
    assert not video_conformant(_v(profile="High 10"))
    assert video_conformant(_v("hevc", "Main 10", 120))
    assert not video_conformant(_v("mpeg4", "Simple"))


def test_high_level_h264_is_reencoded_to_high_41():
    spec = build_plan(_movie(), ROOTS, [_v(level=51), _a("aac", 2)])
    assert spec.needs_transcode and "libx264" in spec.ffmpeg_args
    assert spec.ffmpeg_args[spec.ffmpeg_args.index("-level") + 1] == "4.1"


def test_surround_ac3_copied_and_stereo_aac_added():
    spec = build_plan(_movie(), ROOTS, [_v(), _a("ac3", 6)])
    assert "-c:a:0" in spec.ffmpeg_args and spec.ffmpeg_args.count("-map") == 3
    assert spec.ffmpeg_args[-6:] == ["-c:a:1", "aac", "-ac:a:1", "2", "-b:a:1", "192k"]


def test_dts_becomes_aac_stereo_and_subs_split_by_kind():
    subs = [
        {"codec_type": "subtitle", "codec_name": "ass"},
        {"codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle"},
    ]
    args = build_plan(_movie(), ROOTS, [_v(), _a("dts", 6), *subs]).ffmpeg_args
    assert "-ac:a:0" in args and args.count("-c:a:1") == 0
    assert args[args.index("-c:s:0") + 1] == "srt"
    assert args[args.index("-c:s:1") + 1] == "copy"


def test_tv_special_and_multi_episode_layout():
    item = MediaItem(
        id="i",
        source_path="/in/x.mkv",
        media_type=MediaType.series,
        video_codec="h264",
        canonical_series_name="Show",
        release_year=2020,
        episode_title="Pilot",
        enrichment_data='{"season_number": 0, "episode_number": 1, "episode_end": 2, "tvdb_id": 7}',
    )
    path = build_plan(item, ROOTS, [_v(), _a("aac", 2)]).target_path
    assert path.endswith(
        "/lib/TV/Show (2020) {tvdb-7}/Season 00/Show - S00E01-E02 - Pilot.mkv"
    )


def _enricher(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return VideoEnricher("k", "k", client=client)


def test_enricher_degrades_to_none_on_provider_errors():
    enricher = _enricher(lambda r: httpx.Response(500))
    assert asyncio.run(enricher.movie("X", 2000)) is None
    assert asyncio.run(enricher.episode("X", None, 1, 1)) is None


def test_enricher_unknown_movie_returns_none():
    enricher = _enricher(lambda r: httpx.Response(200, json={"results": []}))
    assert asyncio.run(enricher.movie("Nope", None)) is None


def test_unknown_season_is_placed_in_season_01_not_specials():
    item = MediaItem(
        id="i",
        source_path="/in/x.mkv",
        media_type=MediaType.series,
        video_codec="h264",
        canonical_series_name="Show",
        enrichment_data='{"season_number": null, "episode_number": 5}',
    )
    path = build_plan(item, ROOTS, [_v(), _a("aac", 2)]).target_path
    assert "/Season 01/Show - S01E05" in path
