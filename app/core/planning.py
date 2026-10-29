"""PLAN stage: target path (R-MUSIC-4, R-BOOK-4, R-VIDEO-4/5) and codec args per item."""

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
    tags = meta.get("music", {}).get("tags", {})  # identified tags win (R-MUSIC-5)
    codec = (item.audio_codec or "").lower()
    ext = LOSSY_EXT.get(codec, "flac")
    # audio only: the cover is re-embedded from the best source at EXECUTE (R-MUSIC-3)
    keep = codec in LOSSY_EXT or codec == "flac"
    args = ["-map", "0:a", "-c", "copy" if keep else "flac"]
    artist = (
        tags.get("album_artist")
        or item.album_artist
        or tags.get("artist")
        or item.artist
        or "Unknown Artist"
    )
    album = tags.get("album") or item.album_name or item.album or "Unknown Album"
    year = _year(tags.get("year") or item.release_year or item.year)
    album_dir = f"{album} ({year})" if year else album
    title = (
        tags.get("title")
        or item.title
        or meta.get("track_title")
        or Path(str(item.source_path)).stem
    )
    track = tags.get("track_number") or meta.get("track_number")
    has_track = str(track or "").isdigit()
    prefix = f"{int(str(track)):02d} - " if has_track else ""
    # R-MUSIC-4: disc prefix only for multi-disc; identified tags win, embedded tags are the fallback
    disc_total = int(str(tags.get("disc_total") or meta.get("disc_total") or 1))
    if disc_total > 1:
        disc = tags.get("disc_number") or meta.get("disc_number") or 1
        prefix = f"{disc}-{prefix}" if has_track else f"Disc {disc} - "
    path = confine(root, str(artist), str(album_dir), f"{prefix}{title}.{ext}")
    return PlanSpec(str(path), args, needs_transcode=args[-1] == "flac")


def _audiobook(item: MediaItem, root: str) -> PlanSpec:
    """R-BOOK-4: {Author}/{Series}/{Sequence} - {Title}/{Title}.m4b, series omitted when none."""
    book = _enrichment(item)["book"]
    title, series, sequence = book["title"], book.get("series"), book.get("sequence")
    folder = f"{sequence} - {title}" if series and sequence else title
    parts = [book["author"], *([series] if series else []), folder, f"{title}.m4b"]
    args = book["ffmpeg_args"]
    return PlanSpec(str(confine(root, *parts)), args, needs_transcode="aac" in args)


def _ebook(item: MediaItem, root: str) -> PlanSpec:
    """R-EBOOK-3: Calibre owns the layout; this path is only the nominal Author/Title/Title.ext."""
    book = _enrichment(item)["ebook"]
    title, ext = book["title"], book["format"]
    path = confine(root, book["authors"][0], title, f"{title}.{ext}")
    return PlanSpec(str(path), [], needs_transcode=book["convert"])


H264_PROFILES = {"baseline", "constrained baseline", "main", "high"}
HEVC_PROFILES = {"main", "main 10"}
TEXT_SUBS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}
IMAGE_SUBS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}


def video_conformant(stream: dict | None, fallback_codec: str = "") -> bool:
    """R-VIDEO-1: H.264 High <= L4.1 or HEVC Main/Main10 is kept as-is."""
    if stream is None:  # not probed: trust the codec name alone
        return fallback_codec in VIDEO_COPY_CODECS
    codec = (stream.get("codec_name") or "").lower()
    profile = (stream.get("profile") or "").lower()
    if codec == "h264":
        return profile in H264_PROFILES and int(stream.get("level") or 0) <= 41
    return codec == "hevc" and profile in HEVC_PROFILES


def _audio_args(audio: list[dict]) -> list[str]:
    """AAC stereo for every device, surround AC3/E-AC3 copied; DTS/TrueHD/etc. -> AAC stereo."""
    if not audio:
        return []
    args: list[str] = []
    out = 0
    for i, s in enumerate(audio):
        codec, channels = (
            (s.get("codec_name") or "").lower(),
            int(s.get("channels") or 2),
        )
        if codec in {"ac3", "eac3"} or (codec == "aac" and channels <= 2):
            args += ["-map", f"0:a:{i}", f"-c:a:{out}", "copy"]
        else:
            args += ["-map", f"0:a:{i}", f"-c:a:{out}", "aac", f"-ac:a:{out}", "2"]
            args += [f"-b:a:{out}", "192k"]
        out += 1
    if not any(
        (s.get("codec_name") or "").lower() == "aac"
        and int(s.get("channels") or 2) <= 2
        for s in audio
    ) and not any(a == "aac" for a in args):
        args += ["-map", "0:a:0", f"-c:a:{out}", "aac", f"-ac:a:{out}", "2"]
        args += [f"-b:a:{out}", "192k"]
    return args


def _subtitle_args(subs: list[dict]) -> list[str]:
    """R-VIDEO-2: text subs -> SRT, image subs (PGS/VobSub) copied untouched."""
    args: list[str] = []
    for i, s in enumerate(subs):
        codec = (s.get("codec_name") or "").lower()
        kind = "srt" if codec in TEXT_SUBS else "copy"
        args += ["-map", f"0:s:{i}", f"-c:s:{i}", kind]
    return args


def _video(item: MediaItem, roots: dict[str, str], streams: list[dict]) -> PlanSpec:
    meta = _enrichment(item)
    by_type = {t: [s for s in streams if s.get("codec_type") == t] for t in
               ("video", "audio", "subtitle")}  # fmt: skip
    vcodec = (item.video_codec or "").lower()
    video = by_type["video"][0] if by_type["video"] else None
    keep = video_conformant(video, vcodec)
    if not streams:  # unprobed legacy path: previous generic maps
        a = "copy" if (item.audio_codec or "").lower() in AUDIO_COPY_CODECS else "aac"
        args = [
            "-map",
            "0",
            "-c:v",
            "copy" if keep else "libx264",
            "-c:a",
            a,
            "-c:s",
            "copy",
        ]
    else:
        args = ["-map", "0:v:0", "-c:v", "copy" if keep else "libx264"]
        args += _audio_args(by_type["audio"]) + _subtitle_args(by_type["subtitle"])
    if not keep:  # R-VIDEO-1: everything re-encoded becomes H.264
        args += [
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "20",
            "-profile:v",
            "high",
            "-level",
            "4.1",
        ]
    needs_transcode = (not keep) or "aac" in args
    year = _year(item.release_year or item.guessed_year or meta.get("year"))
    if item.media_type == MediaType.series:
        show = item.canonical_series_name or meta.get("series_title") or "Unknown Show"
        # an unknown season (None) goes to Season 01 for review; only an explicit 0 is Specials
        season_number = meta.get("season_number")
        season, episode = (
            1 if season_number is None else int(season_number),
            int(meta.get("episode_number") or 0),
        )
        end = int(meta.get("episode_end") or episode)
        code = f"S{season:02d}E{episode:02d}" + (
            f"-E{end:02d}" if end > episode else ""
        )
        show_dir = f"{show} ({year})" if year else show
        if meta.get("tvdb_id"):
            show_dir += f" {{tvdb-{meta['tvdb_id']}}}"
        name = f"{sanitize_component(str(show))} - {code}"
        if item.episode_title:
            name += f" - {item.episode_title}"
        path = confine(
            roots["series"], str(show_dir), f"Season {season:02d}", f"{name}.mkv"
        )
    else:
        title = (
            item.canonical_title
            or item.guessed_title
            or meta.get("title")
            or Path(str(item.source_path)).stem
        )
        label = f"{title} ({year})" if year else title
        folder = f"{label} {{tmdb-{item.tmdb_id}}}" if item.tmdb_id else label
        part = f" - part{int(meta['part'])}" if meta.get("part") else ""
        path = confine(
            roots["movie"], str(folder), f"{sanitize_component(str(label))}{part}.mkv"
        )
    return PlanSpec(str(path), args, needs_transcode)


def build_plan(
    item: MediaItem, roots: dict[str, str], streams: list[dict] | None = None
) -> PlanSpec:
    """roots: {"music", "movie", "series"} -> library root. Raises on unsupported types."""
    if item.media_type == MediaType.music:
        return _music(item, roots["music"])
    if item.media_type == MediaType.audiobook:
        return _audiobook(item, roots["audiobook"])
    if item.media_type == MediaType.ebook:
        return _ebook(item, roots["ebook"])
    if item.media_type in (MediaType.movie, MediaType.series):
        return _video(item, roots, streams or [])
    raise ValueError(f"cannot plan media type {item.media_type}")
