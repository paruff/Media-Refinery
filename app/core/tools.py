"""Subprocess helpers: argument lists only, always a timeout, stderr captured (R-SAFE-5)."""

import asyncio
import contextlib
import json

DEFAULT_TIMEOUT = 6 * 3600


TERM_GRACE = 10  # seconds a timed-out tool gets to clean up (e.g. calibredb's database) before SIGKILL


async def run_tool(args: list[str], limit: float = DEFAULT_TIMEOUT):
    """Run a tool; return (returncode, stdout, stderr). Never uses a shell.

    A tool that cannot start (missing binary) is rc 127, not an exception; a timeout sends
    SIGTERM first and SIGKILL only after TERM_GRACE seconds.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except OSError as e:
        return 127, "", f"cannot run {args[0]}: {e}"
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), limit)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), TERM_GRACE)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
        return -1, "", f"timed out after {limit}s: {args[0]}"
    return (
        proc.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


async def probe_duration(path: str, limit: float = 120) -> float | None:
    """Container duration in seconds, or None if ffprobe cannot tell."""
    rc, out, _ = await run_tool(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            path,
        ],
        limit,
    )
    if rc != 0:
        return None
    try:
        return float(json.loads(out)["format"]["duration"])
    except (KeyError, ValueError, TypeError):
        return None
