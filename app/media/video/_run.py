"""Sync subprocess wrapper: argument lists only, always a timeout, stderr captured (R-SAFE-5)."""

import logging
import subprocess
from pathlib import Path

DEFAULT_TIMEOUT = 6 * 3600
logger = logging.getLogger(__name__)


def run(
    command: list[str | Path], check: bool = False, timeout: float = DEFAULT_TIMEOUT
) -> subprocess.CompletedProcess[str] | None:
    """Run a tool. Returns None when it could not start or timed out and check is False."""
    args = [str(c) for c in command]
    try:
        # args are a list, never a shell string
        result = subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("%s failed to run: %s", args[0], exc)
        if check:
            raise
        return None
    if result.returncode != 0:
        logger.error("%s exited %s: %s", args[0], result.returncode, result.stderr)
        if check:
            raise subprocess.CalledProcessError(
                result.returncode, args, output=result.stdout, stderr=result.stderr
            )
    return result
