"""G11 review: container->server path mapping, one rescan per album/run, guarded orchestrator call."""

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.services.notify import Notifier, map_path
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = pytest.mark.asyncio


def cfg(**over):
    base = {
        "PLEX_URL": "http://plex:32400/",
        "PLEX_TOKEN": "pt",
        "PLEX_SECTIONS": {"music": "3", "movie": "1"},
        "JELLYFIN_URL": "http://jf:8096",
        "JELLYFIN_API_KEY": "jk",
        "ABS_URL": "http://abs:80",
        "ABS_TOKEN": "at",
        "ABS_LIBRARY_ID": "lib9",
        "MUSIC_ASSISTANT_URL": "http://ma:8095",
        "MUSIC_ASSISTANT_TOKEN": "mt",
        "NOTIFY_PATH_MAP": {},
    }
    return SimpleNamespace(**{**base, **over})


def notifier(config=None, **kw):
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Notifier(config or cfg(), client, **kw), seen


def names(seen):
    return [f"{r.url.host}{r.url.path}" for r in seen]


# ---- path mapping ---------------------------------------------------------
def test_map_path_uses_the_longest_matching_prefix():
    mapping = {"/output": "/data", "/output/Movies": "/mnt/films"}
    assert map_path("/output/Movies/Dune (2021)", mapping) == "/mnt/films/Dune (2021)"
    assert map_path("/output/Music/A", mapping) == "/data/Music/A"
    assert map_path("/elsewhere/x", mapping) == "/elsewhere/x"
    assert map_path("/outputs/x", mapping) == "/outputs/x"  # whole path segments only


async def test_plex_and_jellyfin_receive_server_side_paths():
    n, seen = notifier(cfg(NOTIFY_PATH_MAP={"/output/Music": "/data/music"}))
    await n.published("music", Path("/output/Music/Artist/Album/01.flac"))
    plex = next(r for r in seen if r.url.host == "plex")
    jf = next(r for r in seen if r.url.host == "jf")
    assert plex.url.params["path"] == "/data/music/Artist/Album"
    assert b"/data/music/Artist/Album" in jf.content


async def test_trailing_slash_in_server_url_does_not_double_the_slash():
    n, seen = notifier()
    await n.published("music", Path("/o/Music/A/B/1.flac"))
    assert "//" not in next(r for r in seen if r.url.host == "plex").url.path


# ---- batching -------------------------------------------------------------
async def test_an_album_causes_one_rescan_per_server_not_one_per_track():
    n, seen = notifier()
    tracks = [Path(f"/o/Music/A/B/{i:02d}.flac") for i in range(12)]
    await n.published_batch("music", tracks)
    assert names(seen).count("plex/library/sections/3/refresh") == 1
    assert names(seen).count("jf/Library/Media/Updated") == 1
    assert names(seen).count("ma/api") == 1


async def test_two_albums_get_two_folder_rescans_but_one_library_wide_sync():
    n, seen = notifier()
    await n.published_batch("music", [Path("/o/M/A/1.flac"), Path("/o/M/B/1.flac")])
    assert names(seen).count("plex/library/sections/3/refresh") == 2
    assert names(seen).count("ma/api") == 1


async def test_schedule_coalesces_publishes_until_flush():
    n, seen = notifier(quiet=3600)  # never fires on its own in the test
    for i in range(5):
        n.schedule("audiobook", Path(f"/o/Books/X/{i}.m4b"))
    assert seen == []
    await n.flush()
    assert names(seen) == ["abs/api/libraries/lib9/scan"]


# ---- orchestrator guard ---------------------------------------------------
async def test_a_notifier_bug_never_fails_the_published_item(tmp_path, caplog):
    cfg_ = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    bad = MagicMock()
    bad.schedule.side_effect = TypeError("PLEX_SECTIONS is not a dict")
    orch = PipelineOrchestrator(factory, cfg_, notifier=bad)
    with caplog.at_level(logging.WARNING):
        orch._notify("music", Path("/o/x.flac"))  # must not raise
    assert "notify" in caplog.text.lower()
    await engine.dispose()
