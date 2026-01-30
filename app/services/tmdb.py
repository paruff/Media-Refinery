import asyncio
import difflib
import logging
from typing import Optional, Dict, Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core import database
from app.models.media import MediaItem

TMDB_API_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_API_KEY = "${TMDB_API_KEY}"
TMDB_RATE_LIMIT = 0.3  # seconds between requests

logger = logging.getLogger("tmdb")

# Simple in-memory LRU cache (can be replaced with DB table)
class LRUCache:
    def __init__(self, max_size=128):
        self.cache = {}
        self.order = []
        self.max_size = max_size

    def get(self, key):
        if key in self.cache:
            self.order.remove(key)
            self.order.insert(0, key)
            return self.cache[key]
        return None

    def set(self, key, value):
        if key in self.cache:
            self.order.remove(key)
        elif len(self.cache) >= self.max_size:
            old = self.order.pop()
            del self.cache[old]
        self.cache[key] = value
        self.order.insert(0, key)

class TMDBService:
    def __init__(self, api_key: str = TMDB_API_KEY, cache: Optional[LRUCache] = None, client: Optional[httpx.AsyncClient] = None):
        self.api_key = api_key
        self.cache = cache or LRUCache()
        self.client = client or httpx.AsyncClient()
        self._lock = asyncio.Lock()

    async def fetch_movie_metadata(self, session: AsyncSession, media_id: int) -> Optional[Dict[str, Any]]:
        # Fetch canonical_title/year from DB (fallback to parsing from source_path if needed)
        stmt = select(MediaItem).where(MediaItem.id == media_id)
        result = await session.execute(stmt)
        media = result.scalar_one_or_none()
        if not media:
            logger.error(f"MediaItem {media_id} not found")
            return None
        # Use canonical_title and release_year if present, else try to parse from source_path
        title = media.canonical_title
        year = media.release_year
        if not title:
            # Fallback: parse from source_path (very basic)
            import re
            m = re.match(r".*/(.+?)(?:[ .(](\d{4}))[)/.].*", media.source_path)
            if m:
                title = m.group(1).replace('.', ' ').replace('_', ' ').strip()
                if not year:
                    try:
                        year = int(m.group(2))
                    except Exception:
                        year = None
            else:
                logger.error(f"No title found for media {media_id}")
                return None
        cache_key = f"{title.lower()}_{year or ''}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.info(f"TMDB cache hit for {cache_key}")
            await self._update_media(session, media, cached)
            return cached
        # Rate limit
        async with self._lock:
            await asyncio.sleep(TMDB_RATE_LIMIT)
            # Primary: title + year
            params = {"api_key": self.api_key, "query": title}
            if year:
                params["year"] = year
            try:
                resp = await self.client.get(TMDB_API_URL, params=params)
            except Exception as e:
                logger.error(f"TMDB request failed: {e}")
                await self._flag_failed(session, media)
                return None
            if resp.status_code == 401:
                logger.error("TMDB unauthorized (401)")
                await self._flag_failed(session, media)
                return None
            if resp.status_code == 429:
                logger.warning("TMDB rate limited (429)")
                await asyncio.sleep(2)
                return await self.fetch_movie_metadata(session, media_id)
            if resp.status_code == 404:
                logger.warning("TMDB not found (404)")
                await self._flag_failed(session, media)
                return None
            data = resp.json()
            results = data.get("results", [])
            # Fallback: title only
            if not results and year:
                params.pop("year")
                resp = await self.client.get(TMDB_API_URL, params=params)
                data = resp.json()
                results = data.get("results", [])
            if not results:
                logger.info(f"No TMDB match for {title}")
                await self._flag_failed(session, media)
                return None
            # Select best match
            best = self._select_best_match(title, results)
            if not best:
                logger.info(f"No suitable TMDB match for {title}")
                await self._flag_failed(session, media)
                return None
            # Prepare canonical data
            canonical = {
                "canonical_title": best["title"],
                "release_year": int(best["release_date"].split("-")[0]) if best.get("release_date") else None,
                "tmdb_id": best["id"],
                "poster_path": best.get("poster_path"),
            }
            self.cache.set(cache_key, canonical)
            await self._update_media(session, media, canonical)
            return canonical

    def _select_best_match(self, title: str, results: list) -> Optional[dict]:
        # Use difflib for title similarity
        for result in results:
            sim = difflib.SequenceMatcher(None, title.lower(), result["title"].lower()).ratio() * 100
            if sim > 90 and result.get("popularity", 0) > 10:
                return result
        # Fallback: first result
        return results[0] if results else None

    async def _update_media(self, session: AsyncSession, media: MediaItem, canonical: dict):
        stmt = (
            update(MediaItem)
            .where(MediaItem.id == media.id)
            .values(
                canonical_title=canonical["canonical_title"],
                release_year=canonical["release_year"],
                tmdb_id=canonical["tmdb_id"],
                poster_path=canonical["poster_path"],
                enrichment_failed=False,
                state="ready_to_plan",
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Media {media.id} enriched with TMDB data")

    async def _flag_failed(self, session: AsyncSession, media: MediaItem):
        stmt = (
            update(MediaItem)
            .where(MediaItem.id == media.id)
            .values(enrichment_failed=True)
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Media {media.id} flagged as enrichment_failed")
