"""G9: `refinery` CLI over the shared services."""

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.core.config import settings
from tests.pipeline_helpers import make_mkv, make_mp3

pytestmark = pytest.mark.integration


@pytest.fixture
def fixtures(tmp_path, monkeypatch):
    for name in ("WORK_DIR", "ARCHIVE_DIR", "QUARANTINE_DIR"):
        monkeypatch.setattr(settings, name, str(tmp_path / name.lower()))
    for name in (
        "MUSIC_ROOT",
        "MOVIES_ROOT",
        "TV_ROOT",
        "AUDIOBOOKS_ROOT",
        "CALIBRE_LIBRARY",
    ):
        monkeypatch.setattr(settings, name, str(tmp_path / "lib" / name.lower()))
    monkeypatch.setattr(settings, "LOG_DIR", str(tmp_path / "logs"))
    src = tmp_path / "fixtures"
    src.mkdir()
    make_mp3(src / "song.mp3", artist="A", album="B", title="C", date="2020", track="1")
    make_mkv(src / "Test Movie (2020).mkv")
    return src


def test_help_lists_every_command():
    out = CliRunner().invoke(app, ["--help"]).output
    for cmd in ("scan", "plan", "approve", "run", "verify", "audit"):
        assert cmd in out


def test_run_dry_run_prints_plan_table_and_writes_nothing_outside_work(
    fixtures, tmp_path
):
    before = {p: p.stat().st_mtime for p in fixtures.iterdir()}
    result = CliRunner().invoke(app, ["run", "--dry-run", str(fixtures)])
    assert result.exit_code == 0, result.output
    assert "song.mp3" in result.output
    assert "Test Movie" in result.output
    assert {p: p.stat().st_mtime for p in fixtures.iterdir()} == before
    assert not (tmp_path / "lib").exists() or not any((tmp_path / "lib").rglob("*.*"))
    assert list((tmp_path / "work_dir" / "dry-run").glob("*.json"))


def test_type_filter_limits_items(fixtures):
    result = CliRunner().invoke(
        app, ["plan", "--dry-run", "--type", "music", str(fixtures)]
    )
    assert result.exit_code == 0, result.output
    assert "copy/tag: 1" in result.output  # the song is planned
    assert "enriched: 1" in result.output  # the movie is classified but out of scope


def test_plan_reports_library_and_writes_nothing(fixtures, tmp_path):
    before = {p: p.stat().st_mtime for p in fixtures.iterdir()}
    result = CliRunner().invoke(app, ["plan", str(fixtures)])  # no --dry-run needed
    assert result.exit_code == 0, result.output
    assert "2 items" in result.output and "estimated disk" in result.output
    assert {p: p.stat().st_mtime for p in fixtures.iterdir()} == before
    assert not (tmp_path / "lib").exists() or not any((tmp_path / "lib").rglob("*.*"))
