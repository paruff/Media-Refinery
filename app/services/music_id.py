"""ENRICH for music: AcoustID fingerprint -> MusicBrainz release (R-MUSIC-5) and cover art (R-MUSIC-3)."""

import asyncio
import io
import json
import logging
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import mutagen
from PIL import Image

from app.core.redact import http_error_summary

logger = logging.getLogger("music_id")

ACOUSTID_URL = "https://api.acoustid.org/v2"
MB_URL = "https://musicbrainz.org/ws/2"
CAA_URL = "https://coverartarchive.org"
USER_AGENT = os.environ.get(
    "MUSICBRAINZ_USER_AGENT",
    "Media-Refinery/1.0 (https://github.com/paruff/Media-Refinery)",
)
MIN_COVER_PX, MAX_COVER_BYTES = 500, 2 * 1024 * 1024  # R-MUSIC-3
FPCALC_TIMEOUT = 120  # seconds (R-SAFE-5)
COVER_NAME = "cover.jpg"


def fpcalc(path: str) -> tuple[int, str] | None:
    """(duration seconds, Chromaprint fingerprint) or None when fpcalc is unavailable."""
    try:
        out = subprocess.run(
            ["fpcalc", "-json", path],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=FPCALC_TIMEOUT,
        ).stdout
        data = json.loads(out)
        return int(data["duration"]), data["fingerprint"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as e:
        logger.warning("fpcalc failed for %s: %s", path, e)
        return None


def jpeg_cover(data: bytes | None) -> bytes | None:
    """Re-encode to JPEG; None if unreadable or smaller than 500 px. Shrinks to <= 2 MB."""
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except OSError, ValueError, Image.DecompressionBombError:
        return None
    img = img.convert("RGB")
    for scale in (1.0, 0.75, 0.5):
        size = (int(img.width * scale), int(img.height * scale))
        if min(size) < MIN_COVER_PX:
            break
        resized = img if scale == 1.0 else img.resize(size)
        for quality in (92, 80, 65):
            buf = io.BytesIO()
            resized.save(buf, "JPEG", quality=quality)
            if buf.tell() <= MAX_COVER_BYTES:
                return buf.getvalue()
    return None


def embedded_cover(path: str | Path) -> bytes | None:
    """First embedded picture (front cover preferred) of a FLAC, MP3/ID3 or M4A file."""
    try:
        audio = mutagen.File(path)
    except mutagen.MutagenError:
        return None
    if audio is None:
        return None
    pictures = getattr(audio, "pictures", None)
    if pictures:  # FLAC
        front = [p for p in pictures if p.type == 3] or pictures
        return bytes(front[0].data)
    tags = audio.tags
    if hasattr(tags, "getall") and (apics := tags.getall("APIC")):  # ID3
        front = [p for p in apics if p.type == 3] or apics
        return bytes(front[0].data)
    if tags is not None and (covr := tags.get("covr")):  # MP4
        return bytes(covr[0])
    return None


def local_cover(path: str | Path) -> bytes | None:
    return jpeg_cover(embedded_cover(path))


def write_album_cover(track: Path) -> bool:
    """cover.jpg next to a published track, taken from the picture embedded in it."""
    target = track.parent / COVER_NAME
    if target.exists():
        return True
    data = embedded_cover(track)
    if data is None:
        return False
    tmp = target.with_name(f".{COVER_NAME}.tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    return True


def _credit(credits: list[dict]) -> str:
    return "".join(c["name"] + c.get("joinphrase", "") for c in credits)


class MusicIdentifier:
    """Never raises: a provider failure or an empty answer yields None (item goes to Review)."""

    def __init__(
        self,
        acoustid_key: str,
        client: httpx.AsyncClient | None = None,
        threshold: float = 0.85,
        fingerprint: Callable[[str], tuple[int, str] | None] = fpcalc,
        mb_interval: float = 1.0,  # MusicBrainz allows one request per second
    ):
        self.key, self.threshold = acoustid_key, threshold
        self.client = client or httpx.AsyncClient(timeout=15, follow_redirects=True)
        self._fingerprint = fingerprint
        self._mb_interval = mb_interval
        self._mb_lock = asyncio.Lock()
        self._last_mb = 0.0
        self._releases: dict[str, dict] = {}  # one fetch per album

    async def identify(self, path: str) -> tuple[float, dict] | None:
        """(AcoustID score, tags keyed like TaggingService) for the best release match."""
        fp = await asyncio.to_thread(self._fingerprint, path)
        if fp is None:
            return None
        try:
            resp = await self.client.get(
                f"{ACOUSTID_URL}/lookup",
                params={
                    "client": self.key,
                    "meta": "recordings releaseids",
                    "duration": fp[0],
                    "fingerprint": fp[1],
                },
            )
            resp.raise_for_status()
            results = sorted(
                resp.json().get("results") or [], key=lambda r: -r.get("score", 0)
            )
            for result in results:
                for rec in result.get("recordings") or []:
                    # ponytail: first release of the recording; prefer the sibling-shared one if albums split
                    if releases := rec.get("releases"):
                        release = await self._release(releases[0]["id"])
                        tags = self._tags(release, rec["id"])
                        return (float(result["score"]), tags) if tags else None
        except (httpx.HTTPError, ValueError, KeyError) as e:
            logger.warning("identify failed for %s: %s", path, http_error_summary(e))
        return None

    async def _release(self, release_id: str) -> dict:
        async with self._mb_lock:
            if release_id not in self._releases:
                wait = self._last_mb + self._mb_interval - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                resp = await self.client.get(
                    f"{MB_URL}/release/{release_id}",
                    params={"inc": "recordings+artist-credits+genres", "fmt": "json"},
                    headers={"User-Agent": USER_AGENT},
                )
                self._last_mb = time.monotonic()
                resp.raise_for_status()
                self._releases[release_id] = resp.json()
            return self._releases[release_id]

    @staticmethod
    def _tags(release: dict, recording_id: str) -> dict | None:
        media = release.get("media") or []
        for medium in media:
            for track in medium.get("tracks") or []:
                if track["recording"]["id"] != recording_id:
                    continue
                credit = track.get("artist-credit") or release["artist-credit"]
                album_credit = release["artist-credit"]
                genres = sorted(
                    release.get("genres") or [], key=lambda g: -g.get("count", 0)
                )
                tags = {
                    "artist": _credit(credit),
                    "album_artist": _credit(album_credit),
                    "album": release["title"],
                    "title": track["title"],
                    "track_number": int(track["position"]),
                    "track_total": int(medium["track-count"]),
                    "disc_number": int(medium["position"]),
                    "disc_total": len(media),
                    "year": (release.get("date") or "")[:4] or None,
                    "genre": genres[0]["name"] if genres else None,
                    "musicbrainz_trackid": recording_id,
                    "musicbrainz_albumid": release["id"],
                    "musicbrainz_artistid": credit[0]["artist"]["id"],
                    "musicbrainz_albumartistid": album_credit[0]["artist"]["id"],
                }
                return {k: v for k, v in tags.items() if v is not None}
        return None

    async def cover(self, path: str, release_id: str | None) -> bytes | None:
        """Embedded picture first, else Cover Art Archive; JPEG, >= 500 px, <= 2 MB."""
        if data := await asyncio.to_thread(local_cover, path):
            return data
        if not release_id:
            return None
        try:
            resp = await self.client.get(f"{CAA_URL}/release/{release_id}/front")
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(
                "cover art lookup failed for %s: %s", release_id, http_error_summary(e)
            )
            return None
        return await asyncio.to_thread(jpeg_cover, resp.content)
