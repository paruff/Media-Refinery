"""probe -> classify -> repair -> smart bitrate -> encode, in one call."""

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from .audio import atmos_stream_index, audio_args
from .encode import encode
from .ffprobe_utils import probe
from .file_classifier import classify_video
from .repair import RepairDispatcher
from .smart_mode import SmartMode

logger = logging.getLogger(__name__)
MIN_BITRATE_KBPS = 200


def convert_video(
    src: Path,
    dst: Path,
    work_dir: Path,
    dry_run: bool = False,
    codec: str = "h264",
    on_event: Callable[[str, str, str], None] | None = None,
) -> Path:
    """Repair `src` if its codec needs it, then encode to `dst`. Never touches `src`.

    `on_event(event, status, detail)` reports the Atmos copy-track decision.

    Raises ValueError when the source cannot be probed or has no video stream.
    """
    info = probe(src, dry_run=dry_run)
    stream = next(
        (s for s in (info or {}).get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if info is None or stream is None:
        raise ValueError(f"cannot read a video stream from {src}")

    dispatcher = RepairDispatcher(work_dir)
    # h264 only needs the remux when it sits in a (broken-prone) AVI
    needs_repair = dispatcher.needs_repair(classify_video(stream)) and (
        classify_video(stream) != "h264" or src.suffix.lower() == ".avi"
    )
    source = src
    if needs_repair:
        try:
            source = dispatcher.dispatch(src, stream, dry_run)
        except (subprocess.SubprocessError, OSError) as exc:
            # a broken repair must not fail a file the encoder may still read
            logger.warning(
                "Repair of %s failed (%s); encoding the original", src.name, exc
            )
            if on_event:
                on_event("repair", "failed", "fell_back_to_original")

    sm = SmartMode()
    bitrate = sm.scale_bitrate(stream, sm.get_bitrate(stream, info.get("format")))
    kbps = max(bitrate // 1000, MIN_BITRATE_KBPS)
    # a repair can reorder streams: map audio by the indices of the file actually encoded
    encoded = info if source == src else (probe(source, dry_run=dry_run) or info)
    audio_streams = [s for s in encoded["streams"] if s.get("codec_type") == "audio"]
    atmos = atmos_stream_index(audio_streams)
    if on_event:
        if atmos is None:
            on_event("audio.atmos", "skipped", "not_detected")
        else:
            on_event("audio.atmos", "included", f"stream_index={atmos}")
    try:
        encode(
            source,
            dst,
            kbps,
            dry_run=dry_run,
            codec=codec,
            audio_args=audio_args(audio_streams),
        )
    finally:
        if source != src and not dry_run:
            source.unlink(missing_ok=True)
    return dst
