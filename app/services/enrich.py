"""ENRICH stage for video: canonical movie (TMDB) and series/episode (TVDB) identity."""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("enrich")

TMDB_URL = "https://api.themoviedb.org/3"
TVDB_URL = "https://api4.thetvdb.com/v4"


@dataclass(frozen=True)
class MovieMatch:
    tmdb_id: int
    title: str
    year: int | None


@dataclass(frozen=True)
class EpisodeMatch:
    tvdb_id: int
    show: str
    year: int | None
    episode_title: str | None


def _year(value) -> int | None:
    text = str(value or "")[:4]
    return int(text) if text.isdigit() else None


class VideoEnricher:
    """Never raises: an unreachable or empty provider yields None (plan falls back to guessit)."""

    def __init__(
        self,
        tmdb_key: str,
        tvdb_key: str,
        client: httpx.AsyncClient | None = None,
        tmdb_url: str = TMDB_URL,
        tvdb_url: str = TVDB_URL,
    ):
        self.tmdb_key, self.tvdb_key = tmdb_key, tvdb_key
        self.client = client or httpx.AsyncClient(timeout=15)
        self.tmdb_url, self.tvdb_url = tmdb_url, tvdb_url
        self._tvdb_token: str | None = None

    async def movie(self, title: str, year: int | None) -> MovieMatch | None:
        params: dict = {"api_key": self.tmdb_key, "query": title}
        if year:
            params["year"] = year
        try:
            resp = await self.client.get(f"{self.tmdb_url}/search/movie", params=params)
            resp.raise_for_status()
            best = next(iter(resp.json().get("results") or []), None)
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("TMDB lookup failed for %r: %s", title, e)
            return None
        if not best:
            return None
        return MovieMatch(best["id"], best["title"], _year(best.get("release_date")))

    async def _tvdb(self, path: str, **params):
        if self._tvdb_token is None:
            login = await self.client.post(
                f"{self.tvdb_url}/login", json={"apikey": self.tvdb_key}
            )
            login.raise_for_status()
            self._tvdb_token = login.json()["data"]["token"]
        resp = await self.client.get(
            f"{self.tvdb_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self._tvdb_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("data")

    async def episode(
        self, show: str, year: int | None, season: int, episode: int
    ) -> EpisodeMatch | None:
        try:
            query: dict = {"query": show, "type": "series"}
            if year:
                query["year"] = year
            found = next(iter(await self._tvdb("/search", **query) or []), None)
            if not found:
                return None
            series_id = int(found["tvdb_id"])
            data = await self._tvdb(
                f"/series/{series_id}/episodes/default",
                season=season,
                episodeNumber=episode,
            )
            first = next(iter((data or {}).get("episodes") or []), None)
        except (httpx.HTTPError, ValueError, KeyError) as e:
            logger.warning("TVDB lookup failed for %r: %s", show, e)
            return None
        return EpisodeMatch(
            series_id,
            found.get("name") or show,
            _year(found.get("year")),
            first.get("name") if first else None,
        )
