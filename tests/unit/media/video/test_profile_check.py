from pathlib import Path

from app.media.video.profile_check import check_profile
from app.models.device_profile import DeviceProfile

PROFILE = DeviceProfile.from_dict(
    {
        "id": "t", "name": "t", "supported_audio": ["aac"], "supported_video": ["h264"],
        "max_resolution": {"width": 1920, "height": 1080}, "container": ["mkv"],
    }
)  # fmt: skip
GOOD = {
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720},
        {"codec_type": "audio", "codec_name": "aac"},
    ]
}


def test_conformant_file_has_no_problems():
    assert check_profile(Path("a.mkv"), GOOD, PROFILE) == []


def test_reports_container_codec_audio_and_size():
    bad = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "mpeg4",
                "width": 3840,
                "height": 2160,
            },
            {"codec_type": "audio", "codec_name": "mp2"},
        ]
    }
    assert len(check_profile(Path("a.avi"), bad, PROFILE)) == 4


def test_no_video_stream():
    assert "no video stream" in check_profile(Path("a.mkv"), {"streams": []}, PROFILE)
