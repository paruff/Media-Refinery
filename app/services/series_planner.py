import re
from pathlib import Path
from app.models.media import MediaItem, MediaType, NormalizationPlan, PlanStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

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


class SeriesPlanningService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(self, media_id: str) -> NormalizationPlan:
        result = await self.db.execute(
            select(MediaItem).where(MediaItem.id == media_id)
        )
        item = result.scalar_one_or_none()
        if not item or item.media_type != MediaType.series:
            raise ValueError("MediaItem not found or not a series")

        # Canonical show name and year
        from typing import cast

        show = clean_title(
            cast(str, item.canonical_series_name)
            or cast(str, item.title)
            or cast(str, item.guessed_title)
            or "Unknown"
        )
        year = (
            cast(str, item.release_year)
            or cast(str, item.guessed_year)
            or cast(str, item.year)
            or "0000"
        )
        ext = (cast(str, item.container) or "mkv").lower()
        season = int(getattr(item, "season_number", 0) or 0)
        episode = int(getattr(item, "episode_number", 0) or 0)
        episode_title = clean_title(cast(str, item.episode_title) or "Episode")

        # Zero-padding
        season_str = f"{season:02d}"
        episode_str = f"{episode:02d}"
        # Specials
        season_folder = f"Season {season_str}" if season > 0 else "Season 00"
        # Folder path
        show_folder = f"{show} ({year})"
        target_dir = Path("/output/series") / show_folder / season_folder
        # Multi-episode support (e.g., S01E01-E02)
        if (
            hasattr(item, "episode_end")
            and item.episode_end
            and item.episode_end != episode
        ):
            episode_end_str = f"{int(item.episode_end):02d}"
            episode_code = f"S{season_str}E{episode_str}-E{episode_end_str}"
        else:
            episode_code = f"S{season_str}E{episode_str}"
        target_file = f"{show_folder} - {episode_code} - {episode_title}.{ext}"
        target_path = target_dir / target_file

        # FFMPEG args (reuse movie logic)
        ffmpeg_args = ["-i", item.source_path]
        vcodec = (item.video_codec or "").lower()
        if vcodec in SUPPORTED_VIDEO_CODECS:
            ffmpeg_args += ["-c:v", "copy"]
        else:
            ffmpeg_args += ["-c:v", "libx264"]
        acodec = (item.audio_codec or "").lower()
        if acodec in SUPPORTED_AUDIO_CODECS:
            ffmpeg_args += ["-c:a", "copy"]
        else:
            ffmpeg_args += ["-c:a", "aac"]
        ffmpeg_args += ["-map", "0", str(target_path)]

        plan = NormalizationPlan(
            media_item_id=item.id,
            target_path=str(target_path),
            ffmpeg_args=ffmpeg_args,
            plan_status=PlanStatus.draft,
            needs_transcode="copy" not in ffmpeg_args,
            needs_rename=True,
            needs_subtitle_conversion=False,
            original_hash="",  # Should be set elsewhere
        )
        self.db.add(plan)
        await self.db.execute(
            update(MediaItem).where(MediaItem.id == item.id).values(state="planned")
        )
        await self.db.commit()
        return plan
