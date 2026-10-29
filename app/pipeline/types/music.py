"""Music: AcoustID/MusicBrainz identity, album-as-unit planning, ReplayGain, tagging."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.models.media import FileState, MediaItem, MediaType
from app.pipeline.types.base import MediaStrategy, flag_review, load_meta
from app.services.music_id import (
    embedded_cover,
    jpeg_cover,
    local_cover,
    write_album_cover,
)
from app.services.replaygain import measure
from app.services.tagging_service import TaggingService

# music items whose source file / album state still matter to their siblings
MUSIC_IN_FLIGHT = (
    FileState.enriched,
    FileState.planned,
    FileState.approved,
    FileState.executing,
    FileState.executed,
    FileState.verified,
)


async def album_pending(o, session, item, unit) -> bool:
    """Album-as-unit: hold until every sibling in the same folder has been classified."""
    folder = unit(o, str(item.source_path))
    rows = await session.execute(
        select(MediaItem.source_path).where(
            MediaItem.state.in_(
                (FileState.pending, FileState.scanning, FileState.scanned)
            )
        )
    )
    return any(unit(o, p) == folder for (p,) in rows)


class MusicStrategy(MediaStrategy):
    async def enrich(self, o, item) -> None:
        """R-MUSIC-5: AcoustID -> MusicBrainz tags. Below the threshold (or no match) the
        embedded tags stay and the plan needs a human."""
        meta = load_meta(item)
        tags = {
            "artist": item.artist,
            "album": item.album,
            "title": item.title or meta.get("track_title"),
            "year": item.year,
            "track_number": meta.get("track_number"),
        }
        tags = {k: v for k, v in tags.items() if v}
        found = (
            await o.identifier.identify(str(item.source_path)) if o.identifier else None
        )
        review = o.identifier is not None and (
            found is None or found[0] < o.identifier.threshold
        )
        if found and not review:
            tags.update(found[1])
            item.album_artist, item.album_name = tags["album_artist"], tags["album"]
            item.release_year = int(tags["year"]) if tags.get("year") else None
            item.disc_number = tags["disc_number"]
            item.mbid, item.release_mbid = (
                tags["musicbrainz_trackid"],
                tags["musicbrainz_albumid"],
            )
        meta["music"] = {
            "tags": tags,
            "score": found[0] if found else None,
            "needs_review": review,
        }
        item.enrichment_data = json.dumps(meta)
        if o.identifier:
            o._emit(
                "identify",
                item.id,
                "degraded" if review else "success",
                "low_confidence" if found and review else "no_match" if review else "",
            )

    async def prepare_plan(self, o, session, item) -> tuple[bool | None, str]:
        if await album_pending(o, session, item, self.unit):
            return False, ""
        await self.check_album_consistency(o, session, item)
        meta = load_meta(item)
        await self.replaygain(o, session, item, meta)
        item.enrichment_data = json.dumps(meta)
        review = ""
        if meta["music"]["needs_review"]:
            review = f"review_required: match score {meta['music']['score']}"
            o._emit("review", item.id, "degraded", review)
        return None, review

    async def replaygain(self, o, session, item, meta) -> None:
        """R-MUSIC-2: track gain from the item, album gain from the folder played as one."""
        tags = meta["music"]["tags"]
        track = await measure([Path(str(item.source_path))])
        folder = Path(str(item.source_path)).parent
        async with o._album_lock:
            if folder not in o._album_gain:
                o._album_gain[folder] = await self._album_replaygain(session, folder)
        album = o._album_gain[folder]
        if track and album:
            tags.update(
                replaygain_track_gain=track[0],
                replaygain_track_peak=track[1],
                replaygain_album_gain=album[0],
                replaygain_album_peak=album[1],
            )
        else:
            o._emit("replaygain", item.id, "skipped", "ffmpeg could not measure")

    @staticmethod
    async def _album_replaygain(session, folder: Path) -> tuple[str, str] | None:
        """Album gain for a folder, stable across restarts: reuse what an in-flight sibling
        already carries, else measure every in-flight sibling whose file is still there."""
        rows = await session.execute(
            select(MediaItem.source_path, MediaItem.enrichment_data).where(
                MediaItem.media_type == MediaType.music,
                MediaItem.state.in_(MUSIC_IN_FLIGHT),
            )
        )
        siblings = [(Path(p), d) for p, d in rows if Path(p).parent == folder]
        for _, data in siblings:
            tags = json.loads(str(data or "{}")).get("music", {}).get("tags", {})
            if tags.get("replaygain_album_gain"):
                return tags["replaygain_album_gain"], tags["replaygain_album_peak"]
        files = sorted(p for p, _ in siblings if p.exists())
        return await measure(files)

    @staticmethod
    async def check_album_consistency(o, session, item) -> None:
        """Tracks of one folder matched to different MusicBrainz releases would publish into
        split album folders: send the whole folder to review."""
        folder = Path(str(item.source_path)).parent
        rows = await session.execute(
            select(MediaItem).where(
                MediaItem.media_type == MediaType.music,
                MediaItem.state.in_((FileState.enriched, FileState.planned)),
            )
        )
        album = [m for m in rows.scalars() if Path(str(m.source_path)).parent == folder]
        releases = {
            load_meta(m).get("music", {}).get("tags", {}).get("musicbrainz_albumid")
            for m in album
        } - {None}
        if len(releases) > 1:
            for m in album:
                flag_review(m, "split_release")
            o._emit("review", item.id, "degraded", "split_release")

    async def build(self, o, item, plan, source: Path, tmp: Path):
        """R-MUSIC-2/3: ffmpeg, then write the tag map and embedded front cover."""
        rc, _, err = await o._run_ffmpeg(str(source), list(plan.ffmpeg_args or []), tmp)
        if rc == 0:
            rc, err = await self._tag(o, item, source, tmp)
        return rc, err, tmp

    @staticmethod
    async def _tag(o, item, source: Path, out: Path) -> tuple[int, str]:
        meta = load_meta(item)["music"]
        cover = await (
            o.identifier.cover(str(source), item.release_mbid)
            if o.identifier
            else asyncio.to_thread(local_cover, source)
        )
        if cover is None:  # below 500 px: keep what the file had rather than drop it
            cover = await asyncio.to_thread(
                lambda: jpeg_cover(embedded_cover(source), min_px=1)
            )
            o._emit(
                "cover",
                item.id,
                "skipped" if cover is None else "degraded",
                "no usable cover (>=500px)",
            )
        tags = {**meta["tags"], "cover": cover}
        # tags from an identified release replace the file's; otherwise merge into them
        clean = item.release_mbid is not None
        if not await asyncio.to_thread(
            TaggingService().apply_tags, str(out), tags, clean
        ):
            return 1, "tagging failed"
        return 0, ""

    async def after_publish(self, o, item, dest: Path) -> None:
        await asyncio.to_thread(write_album_cover, dest)
