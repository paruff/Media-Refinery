"""Tests for encode: hardware encoder selection with libx264/libx265 fallback (R-VIDEO-7)."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.media.video.encode import available_encoders, encode

IN, OUT = Path("/test/input.mkv"), Path("/test/output.mkv")
LISTING = " V....D libx264              libx264 H.264\n V....D h264_nvenc           NVIDIA NVENC\n A....D aac   AAC\n"


def _encode(encoders, results, codec="h264"):
    with (
        patch(
            "app.media.video.encode.available_encoders",
            return_value=frozenset(encoders),
        ),
        patch("subprocess.run", side_effect=results) as run,
    ):
        encode(IN, OUT, 2000, codec=codec)
    return run


class TestEncode:
    def test_hardware_encoder_used_when_listed_and_working(self):
        run = _encode({"h264_videotoolbox"}, [Mock(returncode=0)])
        assert run.call_count == 1
        args = run.call_args[0][0]
        assert "h264_videotoolbox" in args
        assert "2000k" in args

    def test_fallback_to_libx264_when_hardware_fails(self):
        run = _encode({"h264_nvenc"}, [Mock(returncode=1), Mock(returncode=0)])
        assert run.call_count == 2
        args = run.call_args[0][0]
        assert "libx264" in args
        assert "yuv420p" in args

    def test_software_only_when_no_hardware_listed(self):
        run = _encode(set(), [Mock(returncode=0)])
        assert run.call_count == 1
        assert "libx264" in run.call_args[0][0]

    def test_hevc_uses_libx265(self):
        run = _encode(set(), [Mock(returncode=0)], codec="hevc")
        assert "libx265" in run.call_args[0][0]

    def test_vaapi_adds_device_and_hwupload(self):
        run = _encode({"h264_vaapi"}, [Mock(returncode=0)])
        args = run.call_args[0][0]
        assert args.index("-vaapi_device") < args.index("-i")
        assert "format=nv12,hwupload" in args

    def test_software_failure_raises(self):
        with pytest.raises(Exception, match="returned non-zero"):
            _encode(set(), [Mock(returncode=1, stdout="", stderr="boom")])

    def test_rejects_identical_paths(self):
        with pytest.raises(ValueError, match="Input and output paths must differ"):
            encode(IN, IN, 2000)

    def test_dry_run_runs_nothing(self):
        with patch("subprocess.run") as run:
            encode(IN, OUT, 2000, dry_run=True)
        run.assert_not_called()


def test_available_encoders_parses_listing():
    available_encoders.cache_clear()
    with patch(
        "subprocess.run", return_value=Mock(returncode=0, stdout=LISTING, stderr="")
    ):
        assert available_encoders() == {"libx264", "h264_nvenc"}
    available_encoders.cache_clear()


def test_available_encoders_empty_without_ffmpeg():
    available_encoders.cache_clear()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert available_encoders() == frozenset()
    available_encoders.cache_clear()
