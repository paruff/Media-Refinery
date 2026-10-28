"""Movies and series: TMDB/TVDB identity, legacy-codec conversion, VMAF gate."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import cast

from app.core.planning import VIDEO_COPY_CODECS, is_audio_only
from app.core.trace import Status
from app.media.video.convert import convert_video
from app.models.media import MediaType
from app.pipeline.types.base import (
    MediaStrategy,
    flag_review,
    load_meta,
    video_reencoded,
    vmaf_check,
)


class VideoStrategy(MediaStrategy):
    async def enrich(self, o, item) -> None:
        if item.media_type == MediaType.series:
            data = load_meta(item)
            if data.get("season_number") is None or not data.get("episode_number"):
                flag_review(item, "season_or_episode_unknown")
        if o.enricher:
            await self._lookup(o, item)

    @staticmethod
    async def _lookup(o, item) -> None:
        """TMDB (movies) / TVDB (series) identity; a miss keeps the guessit names."""
        meta = load_meta(item)
        if item.media_type == MediaType.movie:
            year = meta.get("year")
            match = await o.enricher.movie(meta.get("title", ""), year)
            if match:
                item.tmdb_id, item.canonical_title = match.tmdb_id, match.title
                item.release_year = match.year or year
                if not match.confident:
                    flag_review(item, "ambiguous_match")
        else:
            match = await o.enricher.episode(
                meta.get("series_title", ""),
                meta.get("year"),
                int(meta.get("season_number") or 0),
                int(meta.get("episode_number") or 0),
            )
            if match:
                item.canonical_series_name, item.release_year = match.show, match.year
                item.episode_title = match.episode_title
                meta["tvdb_id"] = match.tvdb_id
                item.enrichment_data = json.dumps(meta)
                if not match.confident:
                    flag_review(item, "ambiguous_match")
        o._emit(
            "enrich",
            item.id,
            "success" if match else "skipped",
            "no_match" if not match else "",
        )

    @staticmethod
    def is_reencode(item) -> bool:
        """Legacy-codec video (MPEG-1/2, WMV, XviD...) goes through the converter engine."""
        return not is_audio_only(item) and item.video_codec not in VIDEO_COPY_CODECS

    async def build(self, o, item, plan, source: Path, tmp: Path):
        if plan.needs_transcode and self.is_reencode(item):
            rc, err = await self.convert(o, item, source, tmp)  # smart bitrate
            return rc, err, tmp
        rc, _, err = await o._run_ffmpeg(str(source), list(plan.ffmpeg_args or []), tmp)
        return rc, err, tmp

    @staticmethod
    async def convert(o, item, source: Path, out: Path) -> tuple[int, str]:
        def on_event(event: str, status: str, detail: str) -> None:
            o._emit(event, item.id, cast(Status, status), detail)

        try:
            await asyncio.to_thread(
                convert_video, source, out, out.parent / "repair", on_event=on_event
            )
        except subprocess.CalledProcessError as e:
            return 1, f"{e}\n{e.stderr or ''}".strip()
        except Exception as e:
            return 1, str(e)
        return 0, ""

    async def verify(self, o, item, plan, work: Path):
        checks, digest, reason = await super().verify(o, item, plan, work)
        if reason is None and video_reencoded(item, plan):
            reason = await vmaf_check(str(item.source_path), str(work), checks)
        return checks, digest, reason
