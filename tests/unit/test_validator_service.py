from unittest.mock import AsyncMock
from app.services.validator_service import ValidatorService, ValidationReport


def test_validator_path_compliance(tmp_path):
    db = AsyncMock()
    output = tmp_path / "output"
    output.mkdir()
    (output / "music" / "Artist" / "2020 - Album").mkdir(parents=True)
    (output / "music" / "Artist" / "2020 - Album" / "01 - Song.flac").write_bytes(
        b"data"
    )
    validator = ValidatorService(output, tmp_path / "staging", db)
    assert validator._path_compliant("music/Artist/2020 - Album/01 - Song.flac")
    assert not validator._path_compliant("music/Artist/01 - Song.flac")


def test_validator_ffprobe_check(monkeypatch, tmp_path):
    validator = ValidatorService(tmp_path, tmp_path, AsyncMock())
    f = tmp_path / "file.flac"
    f.write_bytes(b"data")
    monkeypatch.setattr("subprocess.check_output", lambda *a, **k: "flac")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: None)
    assert validator._ffprobe_check(f) == ""
    monkeypatch.setattr("subprocess.check_output", lambda *a, **k: "dts")
    assert "DTS" in validator._ffprobe_check(f)


def test_validator_metadata_check(monkeypatch, tmp_path):
    validator = ValidatorService(tmp_path, tmp_path, AsyncMock())
    f = tmp_path / "file.flac"
    f.write_bytes(b"data")
    fake_audio = {"artist": "A", "album": "B", "title": "C", "tracknumber": "1"}
    monkeypatch.setattr("mutagen.File", lambda p: fake_audio)
    assert validator._metadata_check(f) == ""
    fake_audio = {"artist": "A", "album": "B", "title": "C"}
    monkeypatch.setattr("mutagen.File", lambda p: fake_audio)
    assert "Missing tag" in validator._metadata_check(f)


def test_validator_cleanup_staging(tmp_path):
    staging = tmp_path / "staging"
    d = staging / "planid"
    d.mkdir(parents=True)
    (d / "file.flac").write_bytes(b"data")
    validator = ValidatorService(tmp_path, staging, AsyncMock())
    validator._cleanup_staging()
    assert not d.exists()


def test_validator_report_to_dict():
    report = ValidationReport()
    report.total_files = 2
    report.valid = 1
    report.invalid = 1
    report.issues = [{"path": "a", "issue": "b"}]
    d = report.to_dict()
    assert d["total_files"] == 2
    assert d["valid"] == 1
    assert d["invalid"] == 1
    assert d["issues"][0]["path"] == "a"
