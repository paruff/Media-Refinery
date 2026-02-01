import re
from pathlib import Path
from app.models.media import MediaItem, MediaType, NormalizationPlan
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

# Supported codecs for Samsung Series 65
SUPPORTED_VIDEO_CODECS = {"h264", "hevc"}
SUPPORTED_AUDIO_CODECS = {"aac", "ac3"}
UNSAFE_SUBS = {"pgs", "vobsub"}

ILLEGAL_CHAR_MAP = {
    ":": "-",
    "/": "-",
    "\\": "-",
    "?": "",
    "*": "",
    "<": "",
    ">": "",
    "|": "",
    '"': "",
}


def clean_title(title: str) -> str:
    for char, repl in ILLEGAL_CHAR_MAP.items():
        title = title.replace(char, repl)
    return re.sub(r"\s+", " ", title).strip()


class MoviePlanningService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(self, media_id: str) -> NormalizationPlan:
        # Fetch the MediaItem
        result = await self.db.execute(
            select(MediaItem).where(MediaItem.id == media_id)
        )
        item = result.scalar_one_or_none()
        if not item or item.media_type != MediaType.movie:
            raise ValueError("MediaItem not found or not a movie")

        # Extract title/year, clean for path
        from typing import cast

        title = clean_title(
            cast(str, item.title) or cast(str, item.guessed_title) or "Unknown"
        )
        year = cast(str, item.year) or cast(str, item.guessed_year) or "0000"
        ext = (cast(str, item.container) or "mkv").lower()
        target_dir = Path("/output/movies") / f"{title} ({year})"
        target_file = f"{title} ({year}).{ext}"
        target_path = target_dir / target_file

        # Determine ffmpeg args
        ffmpeg_args = ["-i", item.source_path]
        # Video
        vcodec = (item.video_codec or "").lower()
        if vcodec in SUPPORTED_VIDEO_CODECS:
            ffmpeg_args += ["-c:v", "copy"]
        elif vcodec in {"vc-1", "mpeg2", "mpeg-2"}:
            ffmpeg_args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        else:
            ffmpeg_args += ["-c:v", "libx264"]
        # Audio
        acodec = (item.audio_codec or "").lower()
        if acodec in SUPPORTED_AUDIO_CODECS:
            ffmpeg_args += ["-c:a", "copy"]
        elif acodec in {"dts", "dts-hd"}:
            ffmpeg_args += ["-c:a", "aac", "-b:a", "192k"]
        else:
            ffmpeg_args += ["-c:a", "aac"]

        # Subtitles
        needs_subtitle_conversion = False
        subs = item.subtitles
        if subs:
            import json

            try:
                sublist = (
                    json.loads(subs)  # type: ignore[arg-type]
                    if subs.strip().startswith("[")
                    else [s.strip() for s in subs.split(",")]
                )
            except Exception:
                sublist = [subs]
            if any(s.lower() in UNSAFE_SUBS for s in sublist):
                needs_subtitle_conversion = True
        ffmpeg_args += ["-map", "0", str(target_path)]

        # Create NormalizationPlan
        plan = NormalizationPlan(
            media_item_id=item.id,
            target_path=str(target_path),
            ffmpeg_args=ffmpeg_args,
            original_hash="dummy_hash_for_test",
            needs_subtitle_conversion=needs_subtitle_conversion,
        )
        self.db.add(plan)
        # Update MediaItem state
        await self.db.execute(
            update(MediaItem).where(MediaItem.id == item.id).values(state="planned")
        )
        await self.db.commit()
        return plan
