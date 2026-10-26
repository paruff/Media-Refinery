import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.validator_service import ValidatorService


@pytest.fixture
def svc(tmp_path):
    out, stg = tmp_path / "out", tmp_path / "stg"
    out.mkdir()
    stg.mkdir()
    return ValidatorService(out, stg, db=None)


@pytest.mark.parametrize(
    ("rel", "ok"),
    [
        ("music/A/2000 - B/01 - T.flac", True),
        ("movies/M (2000)/M.mkv", True),
        ("tv/S/Season 01/E.mkv", True),
        ("music/short.flac", False),
        ("other/a/b/c.mkv", False),
    ],
)
def test_path_compliant(svc, rel, ok):
    assert svc._path_compliant(rel) is ok


def test_ffprobe_flags_dts(svc):
    with patch("subprocess.check_output", return_value="dts\n"):
        assert svc._ffprobe_check(Path("x.mkv")) == "Unsupported Audio: DTS"


def test_ffprobe_error(svc):
    with patch("subprocess.check_output", side_effect=OSError("nope")):
        assert svc._ffprobe_check(Path("x.mkv")).startswith("ffprobe error")


def test_ffprobe_integrity_error(svc):
    with (
        patch("subprocess.check_output", return_value="aac"),
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")),
    ):
        assert svc._ffprobe_check(Path("x.mkv")).startswith("ffmpeg integrity error")


def test_ffprobe_ok(svc):
    with patch("subprocess.check_output", return_value="aac"), patch("subprocess.run"):
        assert svc._ffprobe_check(Path("x.mkv")) == ""


def test_metadata_unrecognized(svc, tmp_path):
    f = tmp_path / "a.flac"
    f.write_bytes(b"not audio")
    assert svc._metadata_check(f)  # error or unrecognized, never empty


def test_metadata_missing_tag(svc):
    with patch("mutagen.File", return_value={"artist": "x"}):
        assert svc._metadata_check(Path("a.flac")) == "Missing tag: album"


def test_metadata_ok_and_video_skips_tags(svc):
    tags = dict.fromkeys(("artist", "album", "title", "tracknumber"), "x")
    with patch("mutagen.File", return_value=tags):
        assert svc._metadata_check(Path("a.flac")) == ""
    with patch("mutagen.File", return_value={}):
        assert svc._metadata_check(Path("a.mkv")) == ""


def test_cleanup_staging_removes_only_dirs(svc):
    (svc.staging_dir / "job1").mkdir()
    (svc.staging_dir / "keep.txt").write_text("x")
    svc._cleanup_staging()
    assert [p.name for p in svc.staging_dir.iterdir()] == ["keep.txt"]
