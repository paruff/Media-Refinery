import asyncio
import json
from sqlalchemy.future import select
from app.models.media import MediaItem, FileState
import logging
import os


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
            if not os.path.exists(path):
                item.state = FileState.error
                item.error_log = "File not found."
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
                item.state = FileState.scanned
                await session.commit()
            except Exception as e:
                item.state = FileState.error
                item.error_log = str(e)
                await session.commit()

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
