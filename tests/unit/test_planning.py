import json

import pytest

from app.core.planning import build_plan
from app.models.media import MediaItem, MediaType

ROOTS = {"music": "/lib/Music", "movie": "/lib/Movies", "series": "/lib/TV"}


def _item(**kw):
    return MediaItem(id="i", source_path="/in/x", **kw)


def test_lossy_music_is_never_transcoded():
    item = _item(
        media_type=MediaType.music,
        audio_codec="mp3",
        artist="A/B",
        album="Al",
        year="2019-05-01",
        title="Song",
        enrichment_data=json.dumps({"track_number": 3}),
    )
    spec = build_plan(item, ROOTS)
    assert spec.target_path.endswith("/lib/Music/A-B/Al (2019)/03 - Song.mp3")
    assert not spec.needs_transcode and spec.ffmpeg_args[-2:] == ["-c", "copy"]


def test_lossless_music_becomes_flac():
    spec = build_plan(
        _item(media_type=MediaType.music, audio_codec="pcm_s16le", title="T"), ROOTS
    )
    assert spec.target_path.endswith(".flac") and spec.needs_transcode


def test_conformant_video_is_remuxed():
    item = _item(
        media_type=MediaType.movie,
        video_codec="h264",
        audio_codec="aac",
        guessed_title="Movie",
        guessed_year=2020,
        tmdb_id=7,
    )
    spec = build_plan(item, ROOTS)
    assert spec.target_path.endswith(
        "/lib/Movies/Movie (2020) {tmdb-7}/Movie (2020).mkv"
    )
    assert not spec.needs_transcode and "libx264" not in spec.ffmpeg_args


def test_non_conformant_video_becomes_h264():
    item = _item(
        media_type=MediaType.movie,
        video_codec="mpeg4",
        audio_codec="mp3",
        guessed_title="M",
    )
    spec = build_plan(item, ROOTS)
    assert (
        spec.needs_transcode
        and "libx264" in spec.ffmpeg_args
        and "aac" in spec.ffmpeg_args
    )


def test_series_layout():
    item = _item(
        media_type=MediaType.series,
        video_codec="h264",
        audio_codec="aac",
        enrichment_data=json.dumps(
            {"series_title": "Show", "season_number": 1, "episode_number": 2}
        ),
    )
    assert build_plan(item, ROOTS).target_path.endswith(
        "/lib/TV/Show/Season 01/Show - S01E02.mkv"
    )


def test_unknown_type_rejected():
    with pytest.raises(ValueError):
        build_plan(_item(media_type=MediaType.unknown), ROOTS)


def test_music_layout_disc_prefix_only_for_multi_disc(tmp_path):
    from app.core.planning import build_plan

    def plan(disc_total):
        item = MediaItem(
            id="m",
            source_path="/in/a.flac",
            media_type=MediaType.music,
            audio_codec="flac",
            enrichment_data=json.dumps(
                {
                    "music": {
                        "tags": {
                            "album_artist": "Artist",
                            "album": "Album",
                            "title": "Song",
                            "year": "2021",
                            "track_number": 3,
                            "disc_number": 2,
                            "disc_total": disc_total,
                        }
                    }
                }
            ),
        )
        return build_plan(item, {"music": str(tmp_path)}, [])

    assert plan(1).target_path.endswith("Artist/Album (2021)/03 - Song.flac")
    assert plan(2).target_path.endswith("Artist/Album (2021)/2-03 - Song.flac")
    assert plan(1).ffmpeg_args == ["-map", "0:a", "-c", "copy"]
