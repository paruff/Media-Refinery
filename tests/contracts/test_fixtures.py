"""Real parsers against recorded provider responses (G17)."""

import json
from pathlib import Path

import httpx
import pytest

from app.services.enrich import VideoEnricher
from app.services.music_id import MusicIdentifier

FX = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FX / name).read_text())


def client(routes: dict[str, str]) -> httpx.AsyncClient:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load(routes[req.url.path.rsplit("/", 1)[-1]]))

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_tmdb_search_movie():
    e = VideoEnricher("k", "", client({"movie": "tmdb_search_movie.json"}))
    m = await e.movie("Dune", 2021)
    assert (m.tmdb_id, m.title, m.year, m.confident) == (438631, "Dune", 2021, True)


@pytest.mark.asyncio
async def test_tvdb_login_search_episode():
    routes = {
        "login": "tvdb_login.json",
        "search": "tvdb_search.json",
        "default": "tvdb_episodes.json",
    }
    e = VideoEnricher("", "k", client(routes))
    m = await e.episode("Game of Thrones", 2011, 1, 1)
    assert (m.tvdb_id, m.show, m.episode_title) == (
        121361,
        "Game of Thrones",
        "Winter Is Coming",
    )


@pytest.mark.asyncio
async def test_acoustid_and_musicbrainz_to_tags():
    routes = {
        "lookup": "acoustid_lookup.json",
        "b84ee12a-09ef-421b-82de-0441a926375b": "musicbrainz_release.json",
    }
    ident = MusicIdentifier(
        "k", client(routes), fingerprint=lambda _p: (60, "fp"), mb_interval=0
    )
    score, tags = await ident.identify("x.flac")
    assert score == 0.97
    assert tags["artist"] == "Pink Floyd"
    assert tags["album"] == "The Dark Side of the Moon"
    assert (tags["title"], tags["track_number"], tags["track_total"]) == (
        "Speak to Me",
        1,
        10,
    )
    assert tags["year"] == "1973"
    assert tags["musicbrainz_albumid"] == "b84ee12a-09ef-421b-82de-0441a926375b"
