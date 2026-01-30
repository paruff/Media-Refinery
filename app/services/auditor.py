import re
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.media import MediaItem

logger = logging.getLogger("media_refinery.auditor")

ILLEGAL_CHARS = r'[\\/:*?"<>|]'
SUPPORTED_VIDEO_CODECS = {"h264", "hevc", "vp9"}
SUPPORTED_AUDIO_CODECS = {"aac", "ac3"}
HEAVY_CONTAINERS = {"avi", "wmv"}
IMAGE_SUBS = {"pgs", "vobsub"}

class IssueDetectorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def audit(self, media_id: int):
        result = await self.db.execute(select(MediaItem).where(MediaItem.id == media_id))
        item = result.scalar_one_or_none()
        if not item:
            logger.warning(f"Media item {media_id} not found.")
            return
        issues = []
        filename = item.source_path.split('/')[-1]
        # 1. Filename Integrity
        if re.search(ILLEGAL_CHARS, filename):
            issues.append({
                "code": "ILLEGAL_CHAR",
                "level": "critical",
                "message": f"Filename contains illegal character: {filename}"
            })
        # Non-canonical naming
        if item.media_type == "movie":
            if not (item.year or (item.enrichment_data and json.loads(item.enrichment_data).get("year"))):
                issues.append({
                    "code": "MISSING_YEAR",
                    "level": "warning",
                    "message": "Movie is missing year in metadata."
                })
        if item.media_type == "music":
            if not (item.title and item.artist and item.album):
                issues.append({
                    "code": "MISSING_TAGS",
                    "level": "warning",
                    "message": "Music file missing title, artist, or album."
                })
            if not (item.enrichment_data and json.loads(item.enrichment_data).get("track_number")):
                issues.append({
                    "code": "MISSING_TRACK_NUMBER",
                    "level": "warning",
                    "message": "Music file missing track number."
                })
        # 2. Codec & Container (Samsung-Safe)
        if item.video_codec and item.video_codec.lower() not in SUPPORTED_VIDEO_CODECS:
            issues.append({
                "code": "UNSUPPORTED_VIDEO_CODEC",
                "level": "critical",
                "message": f"Video codec {item.video_codec} not supported on Samsung TVs."
            })
        if item.audio_codec and item.audio_codec.lower() not in SUPPORTED_AUDIO_CODECS:
            issues.append({
                "code": "UNSUPPORTED_AUDIO_CODEC",
                "level": "critical",
                "message": f"Audio codec {item.audio_codec} not supported on Samsung TVs."
            })
        if item.container and item.container.lower() in HEAVY_CONTAINERS:
            issues.append({
                "code": "HEAVY_CONTAINER",
                "level": "warning",
                "message": f"Container {item.container} is not recommended. Use MP4/MKV."
            })
        # 3. Subtitle Compatibility
        if item.subtitle_format and item.subtitle_format.lower() in IMAGE_SUBS:
            issues.append({
                "code": "IMAGE_BASED_SUBTITLE",
                "level": "warning",
                "message": f"Subtitle format {item.subtitle_format} is image-based and may not work on TVs."
            })
        if item.has_subtitles and not item.subtitle_language:
            issues.append({
                "code": "MISSING_SUB_LANG",
                "level": "warning",
                "message": "Subtitle track missing language tag."
            })
        # 4. Metadata Gaps
        if item.media_type == "unknown":
            issues.append({
                "code": "UNKNOWN_TYPE",
                "level": "critical",
                "message": "File could not be classified."
            })
        # Store issues
        await self.db.execute(
            update(MediaItem)
            .where(MediaItem.id == media_id)
            .values(
                detected_issues=json.dumps(issues),
                state="audited"
            )
        )
        await self.db.commit()
        logger.info(f"Audited media {media_id}: {len(issues)} issues found.")
        return issues, ("needs_fix" if issues else "ok")
