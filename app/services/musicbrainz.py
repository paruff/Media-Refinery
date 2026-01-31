import asyncio
import difflib
import logging
from typing import Optional, Dict, Any
import musicbrainzngs
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.media import MediaItem

logger = logging.getLogger("musicbrainz")

musicbrainzngs.set_useragent(
    "Media Normalizer", "1.0", "https://github.com/paruff/Media-Refinery"
)
musicbrainzngs.set_rate_limit(limit_or_interval=1.0)


class AlbumCache:
    def __init__(self):
        self.cache = {}  # (artist, album) -> release data

    def get(self, artist, album):
        return self.cache.get((artist.lower(), album.lower()))

    def set(self, artist, album, data):
        self.cache[(artist.lower(), album.lower())] = data


class MusicBrainzService:
    def __init__(self, cache: Optional[AlbumCache] = None):
        self.cache = cache or AlbumCache()
        self._lock = asyncio.Lock()

    async def enrich_music(
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
        artist, album, track_number, title = tokens
        # Album cache
        album_data = self.cache.get(artist, album)
        if not album_data:
            async with self._lock:
                await asyncio.sleep(1.0)  # MusicBrainz rate limit
                try:
                    result = await asyncio.to_thread(
                        musicbrainzngs.search_releases,
                        artist=artist,
                        release=album,
                        limit=1,
                    )
                    releases = result.get("release-list", [])
                    if not releases:
                        logger.info(f"No MusicBrainz release for {artist} - {album}")
                        await self._flag_failed(session, media)
                        return None
                    release_id = releases[0]["id"]
                    # Fetch full release with recordings and artist-credits
                    release_data = await asyncio.to_thread(
                        musicbrainzngs.get_release_by_id,
                        release_id,
                        includes=["recordings", "artist-credits"],
                    )
                    album_data = release_data["release"]
                except Exception as e:
                    logger.error(f"MusicBrainz search failed: {e}")
                    await self._flag_failed(session, media)
                    return None
                self.cache.set(artist, album, album_data)
        # Track matching
        tracks = []
        for med in album_data.get("medium-list", []):
            disc_number = int(med.get("position", 1))
            for tr in med.get("track-list", []):
                tracks.append((disc_number, tr))
        best = None
        for disc, tr in tracks:
            if str(tr.get("number")) == str(track_number):
                tr_title = tr["recording"]["title"]
                sim = (
                    difflib.SequenceMatcher(
                        None, title.lower(), tr_title.lower()
                    ).ratio()
                    * 100
                )
                if sim > 80:
                    best = (disc, tr)
                    break
        if not best:
            logger.info(f"No MusicBrainz track match for {artist} - {album} - {title}")
            await self._flag_failed(session, media)
            return None
        disc_number, track = best
        album_artist = self._get_album_artist(album_data)
        album_name = album_data["title"]
        release_year = None
        if "date" in album_data:
            release_year = int(album_data["date"].split("-")[0])
        mbid = track["recording"]["id"]
        release_mbid = album_data["id"]
        canonical = {
            "album_artist": album_artist,
            "album_name": album_name,
            "release_year": release_year,
            "disc_number": disc_number,
            "mbid": mbid,
            "release_mbid": release_mbid,
        }
        await self._update_media(session, media, canonical)
        return canonical

    def _extract_tokens(self, media: MediaItem):
        import json

        if media.enrichment_data:
            try:
                data = json.loads(media.enrichment_data)
                artist = data.get("artist")
                album = data.get("album")
                track_number = data.get("track_number")
                title = data.get("track_title") or data.get("title")
                if artist and album and track_number and title:
                    return artist, album, track_number, title
            except Exception:
                pass
        return None

    def _get_album_artist(self, album_data):
        credits = album_data.get("artist-credit", [])
        if credits:
            return "".join([c["artist"]["name"] for c in credits if "artist" in c])
        return None

    async def _update_media(
        self, session: AsyncSession, media: MediaItem, canonical: dict
    ):
        stmt = (
            update(MediaItem)
            .where(MediaItem.id == media.id)
            .values(
                album_artist=canonical["album_artist"],
                album_name=canonical["album_name"],
                release_year=canonical["release_year"],
                disc_number=canonical["disc_number"],
                mbid=canonical["mbid"],
                release_mbid=canonical["release_mbid"],
                enrichment_failed=False,
                state="ready_to_plan",
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Media {media.id} enriched with MusicBrainz data")

    async def _flag_failed(self, session: AsyncSession, media: MediaItem):
        stmt = (
            update(MediaItem)
            .where(MediaItem.id == media.id)
            .values(enrichment_failed=True)
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Media {media.id} flagged as enrichment_failed (MusicBrainz)")
