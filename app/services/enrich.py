"""ENRICH stage for video: canonical movie (TMDB) and series/episode (TVDB) identity."""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.core.redact import http_error_summary

logger = logging.getLogger("enrich")

TMDB_URL = "https://api.themoviedb.org/3"
TVDB_URL = "https://api4.thetvdb.com/v4"


RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
MAX_BACKOFF = 10.0


@dataclass(frozen=True)
class MovieMatch:
    tmdb_id: int
    title: str
    year: int | None
    confident: bool = (
        True  # False: first hit of an ambiguous/inexact search, needs a human
    )


@dataclass(frozen=True)
class EpisodeMatch:
    tvdb_id: int
    show: str
    year: int | None
    episode_title: str | None
    confident: bool = True


def _year(value) -> int | None:
    text = str(value or "")[:4]
    return int(text) if text.isdigit() else None


def _norm(title: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _pick(results: list[dict], title: str, year: int | None, name, when):
    """Best hit and whether it is the only plausible one (exact title, matching year if known)."""
    exact = [r for r in results if _norm(name(r)) == _norm(title)]
    if year:
        in_year = [r for r in exact if _year(when(r)) == year]
        exact = in_year or exact
        if in_year:
            return in_year[0], len(in_year) == 1
    if exact:
        return exact[0], len(exact) == 1 and (year is not None or len(results) == 1)
    return (results[0], False) if results else (None, False)


class VideoEnricher:
    """Never raises: an unreachable, rate-limited or empty provider yields None (plan falls back
    to guessit). A lookup is skipped when its provider key is not configured."""

    def __init__(
        self,
        tmdb_key: str,
        tvdb_key: str,
        client: httpx.AsyncClient | None = None,
        tmdb_url: str = TMDB_URL,
        tvdb_url: str = TVDB_URL,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.tmdb_key, self.tvdb_key = tmdb_key, tvdb_key
        self.client = client or httpx.AsyncClient(timeout=15)
        self.tmdb_url, self.tvdb_url = tmdb_url, tvdb_url
        self._sleep = sleep
        self._tvdb_token: str | None = None

    async def _send(self, build) -> httpx.Response:
        """`build()` -> response; retry 429/5xx with Retry-After (capped) backoff."""
        for attempt in range(MAX_ATTEMPTS):
            resp = await build()
            if resp.status_code not in RETRY_STATUS or attempt == MAX_ATTEMPTS - 1:
                return resp
            try:
                wait = float(resp.headers.get("Retry-After", 2**attempt))
            except ValueError:
                wait = 2.0**attempt
            await self._sleep(min(wait, MAX_BACKOFF))
        raise AssertionError("unreachable")  # pragma: no cover

    async def movie(self, title: str, year: int | None) -> MovieMatch | None:
        if not self.tmdb_key:
            return None
        params: dict = {"api_key": self.tmdb_key, "query": title}
        if year:
            params["year"] = year
        try:
            resp = await self._send(
                lambda: self.client.get(f"{self.tmdb_url}/search/movie", params=params)
            )
            resp.raise_for_status()
            best, confident = _pick(
                resp.json().get("results") or [],
                title,
                year,
                lambda r: r.get("title"),
                lambda r: r.get("release_date"),
            )
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(
                "TMDB lookup failed for %r: %s", title, http_error_summary(e)
            )
            return None
        if not best:
            return None
        return MovieMatch(
            best["id"], best["title"], _year(best.get("release_date")), confident
        )

    async def _tvdb(self, path: str, **params):
        """GET with a bearer token; an expired token (401) is replaced once."""
        for attempt in range(2):
            if self._tvdb_token is None:
                login = await self._send(
                    lambda: self.client.post(
                        f"{self.tvdb_url}/login", json={"apikey": self.tvdb_key}
                    )
                )
                login.raise_for_status()
                self._tvdb_token = login.json()["data"]["token"]
            resp = await self._send(
                lambda: self.client.get(
                    f"{self.tvdb_url}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {self._tvdb_token}"},
                )
            )
            if resp.status_code == 401 and attempt == 0:
                self._tvdb_token = None
                continue
            resp.raise_for_status()
            return resp.json().get("data")

    async def episode(
        self, show: str, year: int | None, season: int, episode: int
    ) -> EpisodeMatch | None:
        if not self.tvdb_key:
            return None
        try:
            query: dict = {"query": show, "type": "series"}
            if year:
                query["year"] = year
            found, confident = _pick(
                await self._tvdb("/search", **query) or [],
                show,
                year,
                lambda r: r.get("name"),
                lambda r: r.get("year"),
            )
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
            logger.warning("TVDB lookup failed for %r: %s", show, http_error_summary(e))
            return None
        return EpisodeMatch(
            series_id,
            found.get("name") or show,
            _year(found.get("year")),
            first.get("name") if first else None,
            confident,
        )
