"""probe -> classify -> repair -> smart bitrate -> encode, in one call."""

import logging
from pathlib import Path

from .encode import encode
from .ffprobe_utils import probe
from .file_classifier import classify_video
from .repair import RepairDispatcher
from .smart_mode import SmartMode

logger = logging.getLogger(__name__)
MIN_BITRATE_KBPS = 200


def convert_video(
    src: Path, dst: Path, work_dir: Path, dry_run: bool = False, codec: str = "h264"
) -> Path:
    """Repair `src` if its codec needs it, then encode to `dst`. Never touches `src`.

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
    source = dispatcher.dispatch(src, stream, dry_run) if needs_repair else src

    sm = SmartMode()
    bitrate = sm.scale_bitrate(stream, sm.get_bitrate(stream, info.get("format")))
    kbps = max(bitrate // 1000, MIN_BITRATE_KBPS)
    try:
        encode(source, dst, kbps, dry_run=dry_run, codec=codec)
    finally:
        if source != src and not dry_run:
            source.unlink(missing_ok=True)
    return dst
