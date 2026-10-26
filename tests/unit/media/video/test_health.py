import subprocess
from pathlib import Path
from unittest.mock import patch

from app.media.video.health import health_check, repair_remux

P = Path("/in/a.mkv")


def done(rc=0, err=""):
    return subprocess.CompletedProcess([], rc, "", err)


def test_healthy_file_passes_probe_and_decode_scan():
    with patch("app.media.video.health.run", return_value=done()) as run:
        assert health_check(P) == (True, "")
    assert run.call_count == 2


def test_unreadable_by_ffprobe_skips_the_decode_scan():
    with patch("app.media.video.health.run", return_value=done(1)) as run:
        assert health_check(P) == (False, "ffprobe_unreadable")
    assert run.call_count == 1


def test_decode_errors_on_stderr_fail_even_with_exit_zero():
    with patch("app.media.video.health.run", side_effect=[done(), done(0, "bad")]):
        assert health_check(P) == (False, "ffmpeg_decode_errors")


def test_repair_returns_remuxed_file_only_when_it_is_healthy(tmp_path):
    out = tmp_path / "a_repaired.mkv"
    with (
        patch("app.media.video.health.run", return_value=done()) as run,
        patch("app.media.video.health.health_check", return_value=(True, "")),
    ):
        assert repair_remux(P, tmp_path) == out
    assert "+genpts" in run.call_args[0][0]

    out.write_bytes(b"x")
    with (
        patch("app.media.video.health.run", return_value=done()),
        patch(
            "app.media.video.health.health_check",
            return_value=(False, "ffmpeg_decode_errors"),
        ),
    ):
        assert repair_remux(P, tmp_path) is None
    assert not out.exists()
