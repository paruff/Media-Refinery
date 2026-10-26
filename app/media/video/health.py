"""Health check + remux repair fallback, ported from movies2vlib."""

import logging
from pathlib import Path

from ._run import run

logger = logging.getLogger(__name__)

PROBE_TIMEOUT = 120
DECODE_TIMEOUT = 3600


def health_check(path: Path) -> tuple[bool, str]:
    """ffprobe must read the file and a full decode scan must print no errors.

    Returns (healthy, failure detail); detail is "ffprobe_unreadable" or "ffmpeg_decode_errors".
    """
    probe = run(["ffprobe", "-v", "error", path], timeout=PROBE_TIMEOUT)
    if probe is None or probe.returncode != 0:
        return False, "ffprobe_unreadable"
    scan = run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-f", "null", "-"],
        timeout=DECODE_TIMEOUT,
    )
    if scan is None or scan.returncode != 0 or scan.stderr.strip():
        return False, "ffmpeg_decode_errors"
    return True, ""


def repair_remux(path: Path, work_dir: Path) -> Path | None:
    """Stream-copy to MKV with regenerated timestamps; the result only counts if it is healthy.

    Returns the repaired file, or None when the remux fails or the result is still unhealthy.
    Never touches `path`.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / f"{path.stem}_repaired.mkv"
    result = run(
        [
            *("ffmpeg", "-y", "-nostdin", "-v", "error"),
            *("-fflags", "+genpts", "-err_detect", "ignore_err"),
            *("-i", path, "-c", "copy", out),
        ]
    )
    if result is not None and result.returncode == 0 and health_check(out)[0]:
        return out
    out.unlink(missing_ok=True)
    return None
