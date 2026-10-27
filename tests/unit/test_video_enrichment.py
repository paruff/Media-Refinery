"""G5 review: confident matching, TVDB token refresh + retry, season handling, per-key enabling."""

import json

import httpx
import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import Base, FileState, MediaItem  # noqa: F401
from app.services.classification import ClassificationService
from app.services.enrich import VideoEnricher
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def enricher(handler, tmdb="k", tvdb="k"):
    async def nosleep(_):
        return None

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return VideoEnricher(tmdb, tvdb, client=client, sleep=nosleep)


def movies(*rows):
    return lambda request: httpx.Response(200, json={"results": list(rows)})


def m(id, title, date):
    return {"id": id, "title": title, "release_date": date}


# ---- confidence -----------------------------------------------------------
async def test_exact_title_and_year_is_confident():
    e = enricher(movies(m(1, "Heat", "1995-12-15"), m(2, "Heat", "1986-01-01")))
    match = await e.movie("Heat", 1995)
    assert match.tmdb_id == 1 and match.confident


async def test_same_title_without_a_year_is_ambiguous():
    e = enricher(movies(m(1, "Dune", "2021-10-22"), m(2, "Dune", "1984-12-14")))
    match = await e.movie("Dune", None)
    assert match is not None and not match.confident


async def test_title_that_does_not_match_exactly_is_not_confident():
    e = enricher(movies(m(9, "Heat Wave", "1995-01-01")))
    match = await e.movie("Heat", 1995)
    assert match is not None and not match.confident


async def test_punctuation_and_case_do_not_break_an_exact_match():
    e = enricher(movies(m(5, "Spider-Man: Homecoming", "2017-07-05")))
    assert (await e.movie("spider man homecoming", 2017)).confident


# ---- TVDB resilience ------------------------------------------------------
def tvdb_handler(statuses):
    calls = {"login": 0, "n": 0}

    def handler(request):
        if request.url.path.endswith("/login"):
            calls["login"] += 1
            return httpx.Response(200, json={"data": {"token": f"t{calls['login']}"}})
        status = statuses[min(calls["n"], len(statuses) - 1)]
        calls["n"] += 1
        if status != 200:
            return httpx.Response(status, headers={"Retry-After": "1"})
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200, json={"data": [{"tvdb_id": "7", "name": "Show", "year": "2020"}]}
            )
        return httpx.Response(200, json={"data": {"episodes": [{"name": "Pilot"}]}})

    return handler, calls


async def test_tvdb_expired_token_is_refreshed_once():
    handler, calls = tvdb_handler([401, 200, 200])
    match = await enricher(handler).episode("Show", 2020, 1, 1)
    assert match is not None and match.episode_title == "Pilot"
    assert calls["login"] == 2


async def test_tvdb_rate_limit_is_retried():
    handler, _ = tvdb_handler([429, 200, 200])
    assert (await enricher(handler).episode("Show", 2020, 1, 1)) is not None


async def test_tvdb_persistent_failure_degrades_to_none():
    handler, _ = tvdb_handler([503])
    assert await enricher(handler).episode("Show", 2020, 1, 1) is None


async def test_tmdb_rate_limit_is_retried():
    n = {"i": 0}

    def handler(request):
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"results": [m(1, "Heat", "1995-01-01")]})

    assert (await enricher(handler).movie("Heat", 1995)).tmdb_id == 1


# ---- per-key enabling -----------------------------------------------------
async def test_missing_tmdb_key_skips_movie_lookup_without_a_request():
    def boom(request):
        raise AssertionError("no request expected")

    assert await enricher(boom, tmdb="").movie("Heat", 1995) is None


async def test_missing_tvdb_key_skips_episode_lookup_without_a_request():
    def boom(request):
        raise AssertionError("no request expected")

    assert await enricher(boom, tvdb="").episode("Show", 2020, 1, 1) is None


def test_orchestrator_is_built_with_only_one_key(monkeypatch):
    from app.core.config import settings
    from app.services.refinery import build_orchestrator

    monkeypatch.setattr(settings, "TMDB_API_KEY", "only-tmdb")
    monkeypatch.setattr(settings, "TVDB_API_KEY", "")
    orch = build_orchestrator(
        None, make_config(__import__("pathlib").Path("/tmp/mr-g5"))
    )
    assert orch.enricher is not None


# ---- season / review ------------------------------------------------------
async def _classify(tmp_path, filename):
    base = tmp_path / filename  # one database per call
    base.mkdir()
    engine, factory = await make_session_factory(base)
    async with factory() as s:
        s.add(MediaItem(id="i", source_path=f"/tv/{filename}", state=FileState.pending))
        await s.commit()
        await ClassificationService(s).classify_file("i")
        item = await s.get(MediaItem, "i")
        data = json.loads(item.enrichment_data)
    await engine.dispose()
    return data


async def test_missing_season_is_unknown_not_specials(tmp_path):
    data = await _classify(tmp_path, "Some Show - 05.mkv")
    assert data["season_number"] is None


async def test_explicit_season_zero_and_normal_seasons_survive(tmp_path):
    assert (await _classify(tmp_path, "Show.S00E01.mkv"))["season_number"] == 0
    assert (await _classify(tmp_path, "Show.S02E03.mkv"))["season_number"] == 2


def test_review_flags_block_auto_approval():
    item = MediaItem(
        id="i", enrichment_data=json.dumps({"review": ["ambiguous_match"]})
    )
    assert PipelineOrchestrator._needs_review(item)
    assert not PipelineOrchestrator._needs_review(
        MediaItem(id="j", enrichment_data="{}")
    )
