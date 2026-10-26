import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ._run import run
from .file_classifier import classify_video

logger = logging.getLogger(__name__)

# Rebuild timestamps and ignore stream errors while remuxing (R-VIDEO-6)
_GENPTS = ["-fflags", "+genpts", "-err_detect", "ignore_err"]


def _default_work_dir() -> Path:
    return Path(tempfile.gettempdir()) / "media-refinery-repair"


def _remux(
    path: Path, label: str, suffix: str, pre: list[str], post: list[str],
    work_dir: Path | None, dry_run: bool,
) -> Path:  # fmt: skip
    work_dir = work_dir or _default_work_dir()
    out = work_dir / f"{path.stem}_fixed{suffix}"
    if dry_run:
        logger.info("[DRY-RUN] Would repair %s: %s -> %s", label, path, out)
        return out
    logger.info("Repairing %s: %s", label, path.name)
    work_dir.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-nostdin", *pre, "-i", path, *post, out], check=True)
    logger.info("%s repair complete: %s", label, out.name)
    return out


_COPY = ["-c:v", "copy", "-c:a", "copy"]


def repair_mpeg(
    path: Path, dry_run: bool = False, work_dir: Path | None = None
) -> Path:
    """MPEG-1: regenerate timestamps, stream copy to MKV."""
    return _remux(path, "MPEG-1", ".mkv", _GENPTS, _COPY, work_dir, dry_run)


def repair_mpeg2(
    path: Path, dry_run: bool = False, work_dir: Path | None = None
) -> Path:
    return _remux(path, "MPEG-2", ".mkv", _GENPTS, _COPY, work_dir, dry_run)


def repair_wmv(path: Path, dry_run: bool = False, work_dir: Path | None = None) -> Path:
    """WMV: resync packets by regenerating timestamps."""
    return _remux(path, "WMV", ".mkv", _GENPTS, _COPY, work_dir, dry_run)


def repair_xvid(
    path: Path, dry_run: bool = False, work_dir: Path | None = None
) -> Path:
    """XviD: unpack packed B-frames (stays AVI)."""
    return _remux(
        path,
        "XviD",
        ".avi",
        [],
        ["-c", "copy", "-bsf:v", "mpeg4_unpack_bframes"],
        work_dir,
        dry_run,
    )


def repair_h264_avi(
    path: Path, dry_run: bool = False, work_dir: Path | None = None
) -> Path:
    return _remux(path, "H.264-in-AVI", ".mkv", [], _COPY, work_dir, dry_run)


class RepairDispatcher:
    """Picks the repair for a video stream's codec class."""

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir
        self._repair_map: dict[str, Callable[..., Path]] = {
            "mpeg1": repair_mpeg,
            "mpeg2": repair_mpeg2,
            "wmv": repair_wmv,
            "xvid": repair_xvid,
            "h264": repair_h264_avi,
        }

    def needs_repair(self, codec_type: str) -> bool:
        return codec_type in self._repair_map

    def dispatch(
        self, path: Path, video_stream: dict[str, Any], dry_run: bool = False
    ) -> Path:
        """Repaired path, or the original path when the codec needs no repair."""
        codec_type = classify_video(video_stream)
        if not self.needs_repair(codec_type):
            logger.info("No repair needed for codec: %s", codec_type)
            return path
        logger.info("Dispatching repair for codec: %s", codec_type)
        return self._repair_map[codec_type](path, dry_run, self.work_dir)
