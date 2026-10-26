"""PLAN stage: target path (R-MUSIC-4, R-VIDEO-4/5) and codec args per item."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.paths import confine, sanitize_component
from app.models.media import MediaItem, MediaType

VIDEO_COPY_CODECS = {"h264", "hevc"}  # R-VIDEO-1: conformant video is kept as-is
AUDIO_COPY_CODECS = {"aac", "ac3", "eac3"}
LOSSY_EXT = {
    "mp3": "mp3",
    "aac": "m4a",
    "vorbis": "ogg",
    "opus": "opus",
}  # R-MUSIC-1: never transcoded
IMAGE_CODECS = {"mjpeg", "png", "bmp"}  # cover art reported as a video stream


@dataclass(frozen=True)
class PlanSpec:
    target_path: str
    ffmpeg_args: list[str]  # codec args only; the executor adds -i and the output
    needs_transcode: bool


def is_audio_only(item: MediaItem) -> bool:
    return item.video_codec is None or item.video_codec in IMAGE_CODECS


def _year(value) -> str | None:
    match = re.match(r"\d{4}", str(value or ""))
    return match.group(0) if match else None


def _enrichment(item: MediaItem) -> dict:
    return json.loads(str(item.enrichment_data)) if item.enrichment_data else {}


def _music(item: MediaItem, root: str) -> PlanSpec:
    meta = _enrichment(item)
    codec = (item.audio_codec or "").lower()
    ext = LOSSY_EXT.get(codec, "flac")
    args = (
        ["-map", "0", "-c", "copy"]
        if codec in LOSSY_EXT or codec == "flac"
        else ["-map", "0", "-c:v", "copy", "-c:a", "flac"]
    )
    artist = item.album_artist or item.artist or "Unknown Artist"
    album = item.album_name or item.album or "Unknown Album"
    year = _year(item.release_year or item.year)
    album_dir = f"{album} ({year})" if year else album
    title = item.title or meta.get("track_title") or Path(str(item.source_path)).stem
    track = meta.get("track_number")
    prefix = f"{int(track):02d} - " if str(track or "").isdigit() else ""
    path = confine(root, artist, album_dir, f"{prefix}{title}.{ext}")
    return PlanSpec(str(path), args, needs_transcode=args[-1] == "flac")


def _video(item: MediaItem, roots: dict[str, str]) -> PlanSpec:
    meta = _enrichment(item)
    vcodec, acodec = (item.video_codec or "").lower(), (item.audio_codec or "").lower()
    v = "copy" if vcodec in VIDEO_COPY_CODECS else "libx264"
    a = "copy" if (acodec in AUDIO_COPY_CODECS or not acodec) else "aac"
    args = ["-map", "0", "-c:v", v]
    if v == "libx264":  # R-VIDEO-1: everything re-encoded becomes H.264
        args += ["-pix_fmt", "yuv420p", "-crf", "20"]
    args += ["-c:a", a, "-c:s", "copy"]
    needs_transcode = v != "copy" or a != "copy"
    year = _year(item.release_year or item.guessed_year or meta.get("year"))
    if item.media_type == MediaType.series:
        show = item.canonical_series_name or meta.get("series_title") or "Unknown Show"
        season, episode = (
            int(meta.get("season_number") or 0),
            int(meta.get("episode_number") or 0),
        )
        show_dir = f"{show} ({year})" if year else show
        name = f"{show} - S{season:02d}E{episode:02d}"
        if item.episode_title:
            name += f" - {item.episode_title}"
        path = confine(roots["series"], show_dir, f"Season {season:02d}", f"{name}.mkv")
    else:
        title = (
            item.canonical_title
            or item.guessed_title
            or meta.get("title")
            or Path(str(item.source_path)).stem
        )
        label = f"{title} ({year})" if year else title
        folder = f"{label} {{tmdb-{item.tmdb_id}}}" if item.tmdb_id else label
        path = confine(roots["movie"], folder, f"{sanitize_component(label)}.mkv")
    return PlanSpec(str(path), args, needs_transcode)


def build_plan(item: MediaItem, roots: dict[str, str]) -> PlanSpec:
    """roots: {"music", "movie", "series"} -> library root. Raises on unsupported types."""
    if item.media_type == MediaType.music:
        return _music(item, roots["music"])
    if item.media_type in (MediaType.movie, MediaType.series):
        return _video(item, roots)
    raise ValueError(f"cannot plan media type {item.media_type}")
