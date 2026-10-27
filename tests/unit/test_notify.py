import logging
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.services.notify import Notifier

CFG = SimpleNamespace(
    PLEX_URL="http://plex:32400",
    PLEX_TOKEN="pt",
    PLEX_SECTIONS={"movie": "1", "music": "3"},
    JELLYFIN_URL="http://jf:8096",
    JELLYFIN_API_KEY="jk",
    ABS_URL="http://abs:80",
    ABS_TOKEN="at",
    ABS_LIBRARY_ID="lib9",
    MUSIC_ASSISTANT_URL="http://ma:8095",
    MUSIC_ASSISTANT_TOKEN="mt",
)


def notifier(cfg=CFG, status=200):
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        return httpx.Response(status(req) if callable(status) else status)

    return Notifier(
        cfg, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ), seen


@pytest.mark.asyncio
async def test_movie_hits_plex_and_jellyfin_exactly():
    n, seen = notifier()
    assert await n.published("movie", Path("/m/Dune (2021)/Dune (2021).mkv")) == []
    plex, jf = seen
    assert (plex.method, plex.url.path, plex.url.params["path"]) == (
        "GET",
        "/library/sections/1/refresh",
        "/m/Dune (2021)",
    )
    assert plex.headers["X-Plex-Token"] == "pt"
    assert (jf.method, jf.url.path, jf.headers["X-Emby-Token"]) == (
        "POST",
        "/Library/Media/Updated",
        "jk",
    )
    assert (
        jf.content == b'{"Updates":[{"Path":"/m/Dune (2021)","UpdateType":"Created"}]}'
    )


@pytest.mark.asyncio
async def test_music_hits_plex_jellyfin_music_assistant():
    n, seen = notifier()
    await n.published("music", Path("/mu/A/B/01.flac"))
    assert [r.url.host for r in seen] == ["plex", "jf", "ma"]
    assert seen[0].url.path == "/library/sections/3/refresh"
    ma = seen[2]
    assert ma.url.path == "/api" and b"music/sync" in ma.content
    assert ma.headers["Authorization"] == "Bearer mt"


@pytest.mark.asyncio
async def test_audiobook_hits_audiobookshelf_only():
    n, seen = notifier()
    await n.published("audiobook", Path("/ab/Author/Book/Book.m4b"))
    (abs_,) = seen
    assert (abs_.method, abs_.url.path) == ("POST", "/api/libraries/lib9/scan")
    assert abs_.headers["Authorization"] == "Bearer at"


@pytest.mark.asyncio
async def test_ebook_and_unconfigured_make_no_calls():
    n, seen = notifier()
    await n.published("ebook", Path("/b/x.epub"))
    n2, seen2 = notifier(
        SimpleNamespace(**{**CFG.__dict__, "PLEX_URL": "", "JELLYFIN_URL": ""})
    )
    await n2.published("movie", Path("/m/x.mkv"))
    assert seen == [] and seen2 == []


@pytest.mark.asyncio
async def test_failure_only_warns_and_others_still_run(caplog):
    n, seen = notifier(status=lambda r: 500 if r.url.host == "plex" else 200)
    with caplog.at_level(logging.WARNING, logger="notify"):
        failed = await n.published("movie", Path("/m/D/D.mkv"))
    assert failed == ["plex"] and len(seen) == 2
    assert "plex rescan failed" in caplog.text


@pytest.mark.asyncio
async def test_connection_error_only_warns(caplog):
    def boom(req):
        raise httpx.ConnectError("down")

    n = Notifier(CFG, httpx.AsyncClient(transport=httpx.MockTransport(boom)))
    with caplog.at_level(logging.WARNING, logger="notify"):
        assert await n.published("audiobook", Path("/ab/x.m4b")) == ["audiobookshelf"]
