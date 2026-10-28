"""G19: `refinery doctor` preflight."""

import httpx
import pytest
from typer.testing import CliRunner

from app.cli import app
from app.core.config import Settings
from app.services import doctor

pytestmark = pytest.mark.unit


def _cfg(tmp_path, **kw):
    d = {n: str(tmp_path / n.lower()) for n in (
        "INPUT_DIR", "WORK_DIR", "ARCHIVE_DIR", "QUARANTINE_DIR", "MUSIC_ROOT",
        "MOVIES_ROOT", "TV_ROOT", "AUDIOBOOKS_ROOT", "CALIBRE_LIBRARY")}  # fmt: skip
    return Settings(**d, **kw)


@pytest.mark.asyncio
async def test_missing_tool_unwritable_path_and_dead_server_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(
        doctor.shutil, "which", lambda t: None if t == "fpcalc" else "/x"
    )
    cfg = _cfg(
        tmp_path, ACOUSTID_API_KEY="", PLEX_URL="http://127.0.0.1:1", PLEX_TOKEN="t"
    )
    cfg.WORK_DIR = "/proc/nope/work"
    got = {c.name: c.status for c in await doctor.run_checks(cfg)}
    assert got["tool fpcalc"] == "fail" and got["tool ffmpeg"] == "ok"
    assert got["path WORK_DIR"] == "fail" and got["path INPUT_DIR"] == "ok"
    assert got["key ACOUSTID_API_KEY"] == "warn"
    assert got["server plex"] == "fail"
    assert "tool calibredb" not in got  # ebook is not enabled


def test_cli_exit_code_follows_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.shutil, "which", lambda t: "/x")
    monkeypatch.setattr("app.core.config.settings", _cfg(tmp_path))
    ok = CliRunner().invoke(app, ["doctor"])
    assert ok.exit_code == 0, ok.output
    monkeypatch.setattr(doctor.shutil, "which", lambda t: None)
    assert CliRunner().invoke(app, ["doctor"]).exit_code == 1


def test_httpx_error_type_is_caught():
    assert issubclass(httpx.ConnectError, httpx.HTTPError)
