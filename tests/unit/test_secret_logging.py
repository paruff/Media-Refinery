"""R-SAFE-6: provider API keys and fingerprints never reach the logs (#86, #87)."""

import logging

import httpx
import pytest

from app.core.redact import http_error_summary
from app.main import configure_logging
from app.services.enrich import VideoEnricher
from app.services.music_id import MusicIdentifier

KEY = "SECRET-KEY-123"
FINGERPRINT = "AQADtEyUaFHxFINGERPRINT"


def failing_client(status: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status))
    )


def test_summary_has_type_and_status_but_no_url():
    request = httpx.Request("GET", f"https://x.test/lookup?client={KEY}")
    err = httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(401, request=request)
    )
    assert http_error_summary(err) == "HTTPStatusError (HTTP 401)"
    assert http_error_summary(httpx.ConnectError("no route")) == "ConnectError"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429, 500])
async def test_tmdb_failure_does_not_log_the_key(caplog, status):
    enricher = VideoEnricher(KEY, "tvdb", client=failing_client(status))
    with caplog.at_level(logging.DEBUG):
        assert await enricher.movie("Heat", 1995) is None
    assert "TMDB lookup failed" in caplog.text
    assert KEY not in caplog.text


@pytest.mark.asyncio
async def test_acoustid_failure_does_not_log_key_or_fingerprint(caplog, monkeypatch):
    ident = MusicIdentifier(KEY, client=failing_client(500), mb_interval=0)
    monkeypatch.setattr(ident, "_fingerprint", lambda path: (120, FINGERPRINT))
    with caplog.at_level(logging.DEBUG):
        assert await ident.identify("/x.mp3") is None
    assert "identify failed" in caplog.text
    assert KEY not in caplog.text
    assert FINGERPRINT not in caplog.text


def test_httpx_request_logging_is_silenced(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.settings.LOG_DIR", str(tmp_path))
    logging.getLogger("httpx").setLevel(logging.INFO)
    configure_logging()
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
