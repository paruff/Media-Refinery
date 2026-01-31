import re
from pathlib import Path
from app.models.media import MediaItem, MediaType, NormalizationPlan, PlanStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

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


class MusicPlanningService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(self, media_id: str) -> NormalizationPlan:
        result = await self.db.execute(
            select(MediaItem).where(MediaItem.id == media_id)
        )
        item = result.scalar_one_or_none()
        if not item or item.media_type != MediaType.music:
            raise ValueError("MediaItem not found or not music")

        # Artist folder
        from typing import cast

        artist = clean_title(
            cast(str, item.album_artist) or cast(str, item.artist) or "Unknown Artist"
        )
        # Album folder
        year = str(cast(str, item.release_year) or cast(str, item.year) or "0000")
        album = clean_title(
            cast(str, item.album_name) or cast(str, item.album) or "Unknown Album"
        )
        album_folder = f"{year} - {album}"
        # Disc logic
        disc_number = int(cast(int, item.disc_number) or 1)
        # Track number and title
        track_number = int(getattr(item, "track_number", 0) or 0)
        track_str = f"{track_number:02d}"
        title = clean_title(getattr(item, "title", None) or "Unknown Title")
        ext = (cast(str, item.container) or "flac").lower()

        # Path construction
        base_path = Path("/output/music") / artist / album_folder
        if disc_number > 1:
            base_path = base_path / f"Disc {disc_number:02d}"
        filename = f"{track_str} - {title}.{ext}"
        target_path = base_path / filename

        # Plan
        plan = NormalizationPlan(
            media_item_id=item.id,
            target_path=str(target_path),
            ffmpeg_args=["-i", item.source_path, "-c:a", "copy", str(target_path)],
            plan_status=PlanStatus.draft,
            needs_transcode=False,
            needs_rename=True,
            needs_subtitle_conversion=False,
            needs_tagging=True,
            original_hash="",  # Should be set elsewhere
        )
        self.db.add(plan)
        await self.db.execute(
            update(MediaItem).where(MediaItem.id == item.id).values(state="planned")
        )
        await self.db.commit()
        return plan
