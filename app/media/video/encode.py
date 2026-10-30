import logging
import re
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


_listed: list[frozenset[str]] = []  # one entry once ffmpeg has answered
_broken: set[str] = (
    set()
)  # listed but failed on this host (no device): not retried per file


def reset_encoder_cache() -> None:
    _listed.clear()
    _broken.clear()


def available_encoders() -> frozenset[str]:
    """Encoder names this ffmpeg build lists (empty when ffmpeg cannot run).

    An empty answer is not cached, so a transient failure does not disable hardware for good.
    """
    if _listed:
        return _listed[0]
    result = run(["ffmpeg", "-hide_banner", "-encoders"], timeout=30)
    if result is None or result.returncode != 0:
        return frozenset()
    _listed.append(frozenset(re.findall(r"^ V\S*\s+(\S+)", result.stdout, re.M)))
    return _listed[0]


def _command(
    path: Path, target: Path, bitrate_kbps: int, encoder: str,
    pre: list[str], post: list[str], software: bool, audio: list[str] | None,
) -> list[str | Path]:  # fmt: skip
    video = ["-c:v", encoder, "-b:v", f"{bitrate_kbps}k"]
    if software:
        video += ["-preset", "veryfast"]
    # R-VIDEO-1 / Samsung direct-play on every path: 8-bit 4:2:0, High (h264) or Main (hevc);
    # a 10-bit source is narrowed here. VAAPI converts to nv12 in its filter chain instead.
    if not post:
        video += ["-pix_fmt", "yuv420p"]
    video += ["-profile:v", "main" if "hevc" in encoder or "265" in encoder else "high"]
    # movies2vlib track rule: explicit maps, AAC + E-AC3 (+ copied Atmos), subtitles kept;
    # 0:V skips attached cover art so it is not re-encoded as video
    audio = audio or ["-map", "0:a:0?", "-c:a:0", "aac", "-b:a:0", "192k"]
    tracks = ["-map", "0:V", "-map", "0:s?", *video, *audio, "-c:s", "copy"]
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
        if encoder not in listed or encoder in _broken:
            continue
        logger.info("Encoding %s with %s at %skbps", path.name, encoder, bitrate_kbps)
        result = run(
            _command(path, target, bitrate_kbps, encoder, pre, post, False, audio_args)
        )
        if result is not None and result.returncode == 0:
            return
        _broken.add(encoder)
        logger.warning("%s failed, trying next encoder", encoder)

    software = SOFTWARE_ENCODERS[codec]
    logger.info("Encoding %s with %s at %skbps", path.name, software, bitrate_kbps)
    run(
        _command(path, target, bitrate_kbps, software, [], [], True, audio_args),
        check=True,
    )
