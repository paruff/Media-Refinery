"""Audio track rule (R-VIDEO-1, from movies2vlib): AAC first, an Atmos E-AC3 track copied as-is."""

from typing import Any


def atmos_stream_index(streams: list[dict[str, Any]]) -> int | None:
    """Index of the first E-AC3 stream flagged Atmos by profile or title, else None."""
    for s in streams:
        if s.get("codec_type", "audio") != "audio":
            continue
        if (s.get("codec_name") or "").lower() != "eac3":
            continue
        tags = s.get("tags") or {}
        label = tags.get("title") or tags.get("handler_name") or ""
        if "atmos" in (s.get("profile") or "").lower() or "atmos" in label.lower():
            return int(s["index"])
    return None


def audio_args(streams: list[dict[str, Any]]) -> list[str]:
    """ffmpeg maps/codecs: first track as AAC 192k, plus the Atmos track copied untouched.

    movies2vlib also always synthesised a 640k E-AC3 track; spec R-VIDEO-1 only copies
    existing E-AC3, so that transcode is dropped (it fails Samsung-safe profiles).
    """
    index = atmos_stream_index(streams)
    first = next(
        (s["index"] for s in streams if s.get("codec_type", "audio") == "audio"), None
    )
    if index is not None and index == first:
        # the Atmos track leads: copy it once instead of also encoding an AAC duplicate
        return ["-map", f"0:{index}", "-c:a:0", "copy"]
    args = ["-map", "0:a:0?", "-c:a:0", "aac", "-b:a:0", "192k"]
    if index is not None:
        args += ["-map", f"0:{index}", "-c:a:1", "copy"]
    return args
