import json
import logging
from pathlib import Path
from typing import Any

from ._run import run

logger = logging.getLogger(__name__)


def probe(path: Path, dry_run: bool = False) -> dict[str, Any] | None:
    """ffprobe streams + format as a dict, or None on failure. dry_run returns canned data."""
    if dry_run:
        logger.info("[DRY-RUN] Would probe: %s", path)
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "height": 480,
                    "fps": 30.0,
                    "bit_rate": "1200000",
                }
            ],
            "format": {},
        }

    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            path,
        ],
        timeout=120,
    )
    if result is None or result.returncode != 0:
        logger.error("Failed to probe %s", path)
        return None
    try:
        data: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse ffprobe JSON: %s", e)
        return None
    return data
