import asyncio
import difflib
import logging
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.media import MediaItem

TMDB_API_URL = "https://api.themoviedb.org/3"
TMDB_API_KEY = "${TMDB_API_KEY}"
TMDB_RATE_LIMIT = 0.3  # seconds between requests

logger = logging.getLogger("tmdb.tv")


class TVSeriesCache:
    def __init__(self):
        self.series_id_cache = {}  # title.lower() -> id

    def get(self, title):
        return self.series_id_cache.get(title.lower())

    def set(self, title, series_id):
        self.series_id_cache[title.lower()] = series_id


class TVMetadataService:
    def __init__(
        self,
        api_key: str = TMDB_API_KEY,
        cache: Optional[TVSeriesCache] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key
        self.cache = cache or TVSeriesCache()
        self.client = client or httpx.AsyncClient()
        self._lock = asyncio.Lock()

    async def fetch_series_metadata(
        self, session: AsyncSession, media_id: int
    ) -> Optional[Dict[str, Any]]:
        stmt = select(MediaItem).where(MediaItem.id == media_id)
        result = await session.execute(stmt)
        media = result.scalar_one_or_none()
        if not media:
            logger.error(f"MediaItem {media_id} not found")
            return None
        from typing import cast

        tokens = self._extract_tokens(cast(MediaItem, media))
        if not tokens:
            logger.error(f"No tokens for media {media_id}")
            return None
        title, year, season, episode = tokens
        # Series ID cache
        series_id = self.cache.get(title)
        if not series_id:
            async with self._lock:
                await asyncio.sleep(TMDB_RATE_LIMIT)
                params = {"api_key": self.api_key, "query": title}
                if year:
                    params["first_air_date_year"] = year
                resp = await self.client.get(f"{TMDB_API_URL}/search/tv", params=params)
                if resp.status_code != 200:
                    logger.error(f"TMDB TV search failed: {resp.status_code}")
                    await self._flag_failed(session, media)
                    return None
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    logger.info(f"No TMDB TV match for {title}")
                    await self._flag_failed(session, media)
                    return None
                best = self._select_best_match(title, results)
                if not best:
                    logger.info(f"No suitable TMDB TV match for {title}")
                    await self._flag_failed(session, media)
                    return None
                series_id = best["id"]
                self.cache.set(title, series_id)
        # Episode lookup
        await asyncio.sleep(TMDB_RATE_LIMIT)
        ep_url = f"{TMDB_API_URL}/tv/{series_id}/season/{season}/episode/{episode}"
        params = {"api_key": self.api_key}
        resp = await self.client.get(ep_url, params=params)
        if resp.status_code == 404:
            logger.warning(
                f"TMDB episode not found for {title} S{season:02d}E{episode:02d}"
            )
            await self._flag_mismatch(session, media)
            return None
        if resp.status_code != 200:
            logger.error(f"TMDB episode lookup failed: {resp.status_code}")
            await self._flag_failed(session, media)
            return None
        ep = resp.json()
        canonical = {
            "canonical_series_name": title,
            "episode_title": ep.get("name"),
            "absolute_number": ep.get("episode_number"),
            "overview": ep.get("overview"),
            "series_id": series_id,
        }
        await self._update_media(session, media, canonical)
        return canonical

    def _extract_tokens(self, media: MediaItem):
        # Try to extract from enrichment_data or filename
        import json

        tokens = None
        if media.enrichment_data:
            try:
                data = json.loads(str(media.enrichment_data))
                title = data.get("series_title") or data.get("title")
                year = data.get("year")
                season = data.get("season_number")
                episode = data.get("episode_number")
                if title and season and episode:
                    tokens = (title, year, season, episode)
            except Exception:
                pass
        return tokens

    def _select_best_match(self, title: str, results: list) -> Optional[dict]:
        for result in results:
            sim = (
                difflib.SequenceMatcher(
                    None, title.lower(), result["name"].lower()
                ).ratio()
                * 100
            )
            if sim > 90:
                return result
        return results[0] if results else None

    async def _update_media(
        self, session: AsyncSession, media: MediaItem, canonical: dict
    ):
        stmt = (
            update(MediaItem)
            .where(MediaItem.id == media.id)
            .values(
                canonical_series_name=canonical["canonical_series_name"],
                episode_title=canonical["episode_title"],
                absolute_number=canonical["absolute_number"],
                overview=canonical["overview"],
                tmdb_series_id=canonical["series_id"],
                metadata_mismatch=False,
                state="ready_to_plan",
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Media {media.id} enriched with TMDB TV data")

    async def _flag_failed(self, session: AsyncSession, media: MediaItem):
        stmt = (
            update(MediaItem)
            .where(MediaItem.id == media.id)
            .values(metadata_mismatch=True)
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Media {media.id} flagged as metadata_mismatch")

    async def _flag_mismatch(self, session: AsyncSession, media: MediaItem):
        stmt = (
            update(MediaItem)
            .where(MediaItem.id == media.id)
            .values(metadata_mismatch=True)
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(
            f"Media {media.id} flagged as metadata_mismatch (episode not found)"
        )
