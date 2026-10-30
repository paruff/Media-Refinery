from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.scanner import ScannerService
from app.models.media import FileState, MediaItem


def test_parse_video_audio_subtitle_and_tags():
    item = SimpleNamespace()
    data = {
        "format": {"format_name": "mp4", "tags": {"artist": "A", "date": "1999"}},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "bit_rate": "5000",
                "r_frame_rate": "24/1",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
                "tags": {"language": "eng"},
            },
            {"codec_type": "subtitle", "codec_name": "srt", "tags": {"language": "en"}},
        ],
    }
    ScannerService(MagicMock())._parse_and_update(item, data)
    assert (item.container, item.video_codec, item.video_bitrate) == (
        "mp4",
        "h264",
        5000,
    )
    assert (item.audio_codec, item.audio_channels) == ("aac", "2")
    assert item.has_subtitles is True
    assert (item.artist, item.year) == ("A", "1999")
    assert item.is_standard_compliant is True


def test_parse_non_compliant():
    item = SimpleNamespace()
    ScannerService(MagicMock())._parse_and_update(
        item, {"format": {"format_name": "avi"}, "streams": []}
    )
    assert item.is_standard_compliant is False


@pytest.mark.asyncio
async def test_run_unknown_id_and_missing_file(async_session):
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = async_session
    factory.return_value.__aexit__.return_value = False
    scanner = ScannerService(factory)
    await scanner.run("nope")  # unknown id: logs and returns

    item = MediaItem(source_path="/does/not/exist.mkv")
    async_session.add(item)
    await async_session.commit()
    await scanner.run(item.id)
    assert item.state == FileState.error
    assert item.error_log == "File not found."


def test_cover_art_stream_does_not_replace_the_film_video_codec():
    from types import SimpleNamespace

    from app.core.scanner import ScannerService

    item = SimpleNamespace()
    data = {"streams": [
        {"codec_type": "video", "codec_name": "mpeg4", "width": 160},
        {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
    ], "format": {}}  # fmt: skip
    ScannerService(None)._parse_and_update(item, data)
    assert item.video_codec == "mpeg4" and item.video_width == 160
