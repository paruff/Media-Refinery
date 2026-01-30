import json
import subprocess
from pathlib import Path
import logging
import re

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)


class Metadata:
    def __init__(self):
        self.title = ""
        self.artist = ""
        self.album = ""
        self.year = ""
        self.genre = ""
        self.comment = ""
        self.track = ""
        self.track_total = ""
        self.disc = ""
        self.disc_total = ""
        self.album_artist = ""
        self.composer = ""
        self.show = ""
        self.season = ""
        self.episode = ""
        self.director = ""
        self.actors = []
        self.duration = 0.0
        self.bitrate = 0
        self.sample_rate = 0
        self.channels = 0
        self.format = ""
        self.file_path = ""


class MetadataExtractor:
    def __init__(self, cleanup_tags=False):
        self.cleanup_tags = cleanup_tags

    def extract_metadata(self, path):
        meta = Metadata()
        meta.file_path = path
        meta.format = Path(path).suffix.lstrip(".")

        try:
            output = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    path,
                ],
                text=True,
            )
            result = json.loads(output)

            tags = {
                k.lower(): v
                for k, v in result.get("format", {}).get("tags", {}).items()
            }

            meta.title = self.get_tag(tags, "title")
            meta.artist = self.get_tag(tags, "artist")
            meta.album = self.get_tag(tags, "album")
            meta.album_artist = self.get_tag(tags, "album_artist", "albumartist")
            meta.year = self.get_tag(tags, "year", "date")
            meta.genre = self.get_tag(tags, "genre")
            meta.track = self.get_tag(tags, "track", "tracknumber")
            meta.composer = self.get_tag(tags, "composer")
            meta.comment = self.get_tag(tags, "comment")

            meta.duration = float(result.get("format", {}).get("duration", 0))
            meta.bitrate = int(result.get("format", {}).get("bit_rate", 0))

            for stream in result.get("streams", []):
                if stream.get("codec_type") == "audio":
                    meta.sample_rate = int(stream.get("sample_rate", 0))
                    meta.channels = stream.get("channels", 0)
                    break

        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning("ffprobe failed", extra={"error": str(e), "path": path})
            self.parse_filename(meta, path)
        return meta

    def get_tag(self, tags, *keys):
        for key in keys:
            if key in tags:
                return tags[key]
        return ""

    def parse_filename(self, meta, path):
        basename = Path(path).stem
        match = re.match(r"^(.*)\.S(\d{2})E(\d{2})", basename, re.IGNORECASE)
        if match:
            meta.show = match.group(1).replace(".", " ").strip()
            meta.season = match.group(2)
            meta.episode = match.group(3)
            meta.title = meta.show

    def clean_tag(self, tag):
        return tag.strip() if tag else tag
