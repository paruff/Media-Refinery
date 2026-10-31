from pathlib import Path
from unittest.mock import patch

import pytest

from app.media.video.convert import convert_video

SRC, DST, WORK = Path("/in/a.mpg"), Path("/out/a.mkv"), Path("/work")
INFO = {
    "streams": [{"codec_type": "video", "codec_name": "mpeg1video", "height": 480, "r_frame_rate": "25/1", "bit_rate": "1000000"}],
    "format": {},
}  # fmt: skip


def test_repairs_then_encodes_at_smart_bitrate():
    fixed = WORK / "a_fixed.mkv"
    with (
        patch("app.media.video.convert.probe", return_value=INFO),
        patch(
            "app.media.video.convert.RepairDispatcher.dispatch", return_value=fixed
        ) as repair,
        patch("app.media.video.convert.encode") as enc,
    ):
        convert_video(SRC, DST, WORK)
    repair.assert_called_once()
    assert enc.call_args[0][:2] == (fixed, DST)
    assert enc.call_args[0][2] == 1200  # SD factor 1.2 x 1000 kbps


def test_conformant_h264_mkv_is_not_remuxed():
    info = {
        "streams": [{"codec_type": "video", "codec_name": "h264", "height": 1080}],
        "format": {},
    }
    with (
        patch("app.media.video.convert.probe", return_value=info),
        patch("app.media.video.convert.RepairDispatcher.dispatch") as repair,
        patch("app.media.video.convert.encode") as enc,
    ):
        convert_video(Path("/in/a.mkv"), DST, WORK)
    repair.assert_not_called()
    assert enc.call_args[0][0] == Path("/in/a.mkv")


def test_unreadable_source_raises():
    with (
        patch("app.media.video.convert.probe", return_value=None),
        pytest.raises(ValueError),
    ):
        convert_video(SRC, DST, WORK)


def test_atmos_index_comes_from_the_file_actually_encoded():
    """After a repair the stream order can change: probe the repaired file's audio."""
    fixed = WORK / "a_fixed.mkv"
    eac3 = {
        "codec_type": "audio",
        "codec_name": "eac3",
        "profile": "Dolby Digital Plus + Dolby Atmos",
    }
    original = {**INFO, "streams": [*INFO["streams"], {**eac3, "index": 1}]}
    repaired = {
        **INFO,
        "streams": [
            *INFO["streams"],
            {"codec_type": "audio", "codec_name": "aac", "index": 1},
            {**eac3, "index": 2},
        ],
    }
    probes = {SRC: original, fixed: repaired}
    with (
        patch(
            "app.media.video.convert.probe",
            side_effect=lambda p, dry_run=False: probes[p],
        ),
        patch("app.media.video.convert.RepairDispatcher.dispatch", return_value=fixed),
        patch("app.media.video.convert.encode") as enc,
    ):
        convert_video(SRC, DST, WORK)
    assert "0:2" in enc.call_args.kwargs["audio_args"]


def test_failed_repair_falls_back_to_encoding_the_original():
    import subprocess

    events = []
    with (
        patch("app.media.video.convert.probe", return_value=INFO),
        patch(
            "app.media.video.convert.RepairDispatcher.dispatch",
            side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
        ),
        patch("app.media.video.convert.encode") as enc,
    ):
        convert_video(SRC, DST, WORK, on_event=lambda *a: events.append(a))
    assert enc.call_args[0][0] == SRC
    assert ("repair", "failed", "fell_back_to_original") in events
