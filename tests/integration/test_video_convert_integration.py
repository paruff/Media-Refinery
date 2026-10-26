"""Generated legacy-codec samples -> MKV that passes the samsung_tizen profile check (G3)."""

import subprocess

import pytest

from app.media.video.convert import convert_video
from app.media.video.ffprobe_utils import probe
from app.media.video.profile_check import check_profile
from app.services.device_profile_service import DeviceProfileService

# (name, container, video encoder args, audio encoder args, expected source codec)
SAMPLES = [
    ("mpeg1", "mpg", ["-c:v", "mpeg1video"], ["-c:a", "mp2"], "mpeg1video"),
    (
        "wmv",
        "wmv",
        ["-c:v", "wmv2"],
        ["-c:a", "wmav2"],
        "wmv2",
    ),  # ffmpeg cannot encode wmv3
    ("xvid", "avi", ["-c:v", "mpeg4", "-vtag", "XVID"], ["-c:a", "mp3"], "mpeg4"),
]


def _generate(path, v_args, a_args):
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-v", "error",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         *v_args, *a_args, str(path)],
        check=True,
    )  # fmt: skip


@pytest.mark.parametrize(
    "name,ext,v_args,a_args,codec", SAMPLES, ids=[s[0] for s in SAMPLES]
)
def test_legacy_sample_converts_to_samsung_safe_mkv(
    tmp_path, name, ext, v_args, a_args, codec
):
    src, dst = tmp_path / f"{name}.{ext}", tmp_path / f"{name}.mkv"
    _generate(src, v_args, a_args)
    assert probe(src)["streams"][0]["codec_name"] == codec

    convert_video(src, dst, tmp_path / "work")

    assert src.exists()  # R-SAFE-1: original untouched
    profile = DeviceProfileService().get_profile("samsung_tizen")
    assert check_profile(dst, probe(dst), profile) == []
    assert not list(
        (tmp_path / "work").glob("*_fixed*")
    )  # repair intermediates cleaned up
