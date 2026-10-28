import logging
import re
from functools import lru_cache
from pathlib import Path

from ._run import run

logger = logging.getLogger(__name__)

VAAPI_DEVICE = "/dev/dri/renderD128"
SOFTWARE_ENCODERS = {"h264": "libx264", "hevc": "libx265"}
# (encoder, args before -i, args after -i); first one both listed by ffmpeg and working wins
HARDWARE_ENCODERS: dict[str, list[tuple[str, list[str], list[str]]]] = {
    "h264": [
        ("h264_videotoolbox", [], []),
        ("h264_nvenc", [], []),
        (
            "h264_vaapi",
            ["-vaapi_device", VAAPI_DEVICE],
            ["-vf", "format=nv12,hwupload"],
        ),
    ],
    "hevc": [
        ("hevc_videotoolbox", [], []),
        ("hevc_nvenc", [], []),
        (
            "hevc_vaapi",
            ["-vaapi_device", VAAPI_DEVICE],
            ["-vf", "format=nv12,hwupload"],
        ),
    ],
}


@lru_cache(maxsize=1)
def available_encoders() -> frozenset[str]:
    """Encoder names this ffmpeg build lists (empty when ffmpeg cannot run)."""
    result = run(["ffmpeg", "-hide_banner", "-encoders"], timeout=30)
    if result is None or result.returncode != 0:
        return frozenset()
    return frozenset(re.findall(r"^ V\S*\s+(\S+)", result.stdout, re.M))


def _command(
    path: Path, target: Path, bitrate_kbps: int, encoder: str,
    pre: list[str], post: list[str], software: bool, audio: list[str] | None,
) -> list[str | Path]:  # fmt: skip
    video = ["-c:v", encoder, "-b:v", f"{bitrate_kbps}k"]
    if software:
        video += [
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
        ]  # R-VIDEO-1 High profile
    # movies2vlib track rule: explicit maps, AAC + E-AC3 (+ copied Atmos), subtitles kept
    tracks = (
        ["-map", "0:V", "-map", "0:s?", *video, *audio, "-c:s", "copy"]
        if audio
        else [*video, "-c:a", "aac", "-b:a", "192k"]
    )
    return ["ffmpeg", "-y", "-nostdin", *pre, "-i", path, *post, *tracks, target]


def encode(
    path: Path,
    target: Path,
    bitrate_kbps: int,
    dry_run: bool = False,
    codec: str = "h264",
    audio_args: list[str] | None = None,
) -> None:
    """Encode to `codec` (h264|hevc) + AAC. Hardware encoder when one works, else libx264/libx265.

    Raises ValueError if input and output are the same file; CalledProcessError if the
    software fallback fails too.
    """
    if path.resolve() == target.resolve():
        raise ValueError("Input and output paths must differ.")
    if dry_run:
        logger.info(
            "[DRY-RUN] Would encode %s to %s at %skbps", path, target, bitrate_kbps
        )
        return

    listed = available_encoders()
    for encoder, pre, post in HARDWARE_ENCODERS[codec]:
        if encoder not in listed:
            continue
        logger.info("Encoding %s with %s at %skbps", path.name, encoder, bitrate_kbps)
        result = run(
            _command(path, target, bitrate_kbps, encoder, pre, post, False, audio_args)
        )
        if result is not None and result.returncode == 0:
            return
        logger.warning("%s failed, trying next encoder", encoder)

    software = SOFTWARE_ENCODERS[codec]
    logger.info("Encoding %s with %s at %skbps", path.name, software, bitrate_kbps)
    run(
        _command(path, target, bitrate_kbps, software, [], [], True, audio_args),
        check=True,
    )
