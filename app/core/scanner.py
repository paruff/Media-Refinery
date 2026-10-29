import asyncio
import json
import logging
import os
from pathlib import Path

from sqlalchemy.future import select

from app.media.ebook import is_ebook
from app.models.media import FileState, MediaItem


def _is_audio_only(data):
    """True when ffprobe found audio and no real video (cover art doesn't count)."""
    streams = data.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    has_video = any(
        s.get("codec_type") == "video"
        and not s.get("disposition", {}).get("attached_pic")
        for s in streams
    )
    return has_audio and not has_video


class ScannerService:
    def __init__(self, db_session_factory, logger=None):
        self.db_session_factory = db_session_factory
        self.logger = logger or logging.getLogger("ScannerService")

    async def run(self, media_id):
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(MediaItem).where(MediaItem.id == media_id)
            )
            item = result.scalar_one_or_none()
            if not item:
                self.logger.error(f"MediaItem {media_id} not found.")
                return
            if item.state != FileState.scanning:
                item.state = FileState.scanning
                await session.commit()
            path = item.source_path
            if not await asyncio.to_thread(os.path.exists, path):
                item.state = FileState.error
                item.error_log = "File not found."
                await session.commit()
                return
            if is_ebook(path):  # no streams to probe; Calibre reads these (R-EBOOK-2)
                item.container = Path(path).suffix.lstrip(".").lower()
                item.state = FileState.scanned
                await session.commit()
                return
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    item.state = FileState.error
                    item.error_log = stderr.decode()
                    await session.commit()
                    return
                data = json.loads(stdout.decode())
                self._parse_and_update(item, data)

                # --- FINGERPRINTING & DUPLICATE DETECTION (type known only after probe) ---
                duplicate = await self._fingerprint_is_duplicate(
                    session, item, path, _is_audio_only(data)
                )
                if duplicate:
                    item.state = FileState.error
                    item.error_log = (
                        f"Duplicate {duplicate} fingerprint detected. Skipping."
                    )
                    await session.commit()
                    return

                # Run pre-clean detection and record issues
                from app.services.preclean import PrecleanDetector

                detector = PrecleanDetector()
                metadata = {
                    "Title": item.title,
                    "Year": item.year,
                    "Season/Episode": (
                        str(item.absolute_number)
                        if getattr(item, "absolute_number", None)
                        else None
                    ),
                    "Artist/Album": (
                        f"{item.artist}/{item.album}"
                        if (item.artist or item.album)
                        else None
                    ),
                }

                flags = detector.scan_metadata_dict(metadata)

                # Filename checks
                basename = os.path.basename(path)
                if detector.contains_non_utf8(basename):
                    flags.append("non_utf8_filename")
                illegal = detector.illegal_filesystem_chars(basename)
                for c in illegal:
                    flags.append(f"illegal_char:{c}")

                # Classification
                classification = detector.classify_unplaced(Path(path))
                if classification == "unclassified":
                    flags.append("unclassified")

                item.detected_issues = json.dumps(flags)

                item.state = FileState.scanned
                await session.commit()
            except Exception as e:
                self.logger.exception(f"Scan failed for {item.id}")
                item.state = FileState.error
                item.error_log = str(e)
                await session.commit()

    async def _fingerprint_is_duplicate(self, session, item, path, audio_only):
        """Fingerprint `item` and return "audio"/"video" if another item matches."""
        from app.services.fingerprint_service import FingerprintService

        if audio_only:
            kind, column = "audio", MediaItem.audio_fingerprint
            fp = await asyncio.to_thread(FingerprintService.fingerprint_audio, path)
            item.audio_fingerprint = fp
        else:
            kind, column = "video", MediaItem.video_fingerprint
            fp = await asyncio.to_thread(FingerprintService.fingerprint_video, path)
            item.video_fingerprint = fp
        if not fp:
            return None
        query = select(MediaItem.id).where(column == fp, MediaItem.id != item.id)
        if audio_only and item.album:
            # Same recording on a compilation and its studio album is not a duplicate (#178)
            query = query.where(MediaItem.album == item.album)
        # limit(1): any number of existing matches is just "a duplicate"
        dup = await session.execute(query.limit(1))
        return kind if dup.first() else None

    def _parse_and_update(self, item, data):
        # Container
        item.container = data.get("format", {}).get("format_name")
        # Streams
        streams = data.get("streams", [])
        for stream in streams:
            if stream.get("codec_type") == "video":
                item.video_codec = stream.get("codec_name")
                item.video_width = stream.get("width")
                item.video_height = stream.get("height")
                item.video_bitrate = int(stream.get("bit_rate", 0) or 0)
                item.video_fps = str(stream.get("r_frame_rate"))
            elif stream.get("codec_type") == "audio":
                item.audio_codec = stream.get("codec_name")
                item.audio_channels = str(stream.get("channels"))
                item.audio_language = stream.get("tags", {}).get("language")
            elif stream.get("codec_type") == "subtitle":
                item.has_subtitles = True
                item.subtitle_format = stream.get("codec_name")
                item.subtitle_language = stream.get("tags", {}).get("language")
        # Music tags
        tags = data.get("format", {}).get("tags", {})
        item.artist = tags.get("artist")
        item.album = tags.get("album")
        item.title = tags.get("title")
        item.year = tags.get("date")
        # Compliance (example: Samsung-safe)
        item.is_standard_compliant = (item.container in ("mp4", "mkv")) and (
            item.video_codec in ("h264", "hevc")
        )
