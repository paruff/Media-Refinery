"""VERIFY stage: generic spec §6 checks (decode, duration, sha256)."""

import asyncio
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from itertools import pairwise

from app.core.tools import probe_duration, run_tool

AUDIO_TOLERANCE = 0.5  # seconds
VIDEO_TOLERANCE = 1.0
REASONS = {
    "decode": "decode_failed",
    "duration": "duration_mismatch",
    "flac": "flac_test_failed",
    "chapters": "chapter_count_mismatch",
    "epubcheck": "epubcheck_failed",
}


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


async def _flac_test(output: str) -> Check:
    if (
        shutil.which("flac") is None
    ):  # R-MUSIC requires flac -t; a skipped test is not a pass
        return Check("flac", False, "flac is not installed")
    rc, _, err = await run_tool(["flac", "-t", "-s", output], 3600)
    return Check("flac", rc == 0, err.strip()[:500])


async def _chapter_check(output: str, expected: int) -> Check:
    rc, out, _ = await run_tool(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_chapters",
            "-show_format",
            "-of",
            "json",
            output,
        ],
        120,
    )
    try:
        data = json.loads(out) if rc == 0 else {}
        chapters = [
            (float(c["start_time"]), float(c["end_time"]))
            for c in data.get("chapters", [])
        ]
        duration = float(data.get("format", {}).get("duration") or 0)
    except ValueError, KeyError:
        chapters, duration = [], 0.0
    found = len(chapters)
    ordered = all(a[1] <= b[0] + 0.01 and a[0] < a[1] for a, b in pairwise(chapters))
    in_bounds = not chapters or chapters[-1][1] <= duration + AUDIO_TOLERANCE
    ok = found >= 1 and found == expected and ordered and in_bounds
    detail = (
        f"{found}/{expected}"
        + ("" if ordered else " out of order")
        + ("" if in_bounds else " past end")
    )
    return Check("chapters", ok, detail)


async def verify_output(
    source: str,
    output: str,
    is_audio: bool,
    expected_duration: float | None = None,  # merged inputs: the sum of the sources
    expected_chapters: int | None = None,
):
    """Return (checks as dicts, output sha256, quarantine reason or None)."""
    rc, _, err = await run_tool(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", output, "-f", "null", "-"], 3600
    )
    checks = [Check("decode", rc == 0 and not err.strip(), err.strip()[:500])]
    src_dur = expected_duration or await probe_duration(source)
    out_dur = await probe_duration(output)
    tolerance = AUDIO_TOLERANCE if is_audio else VIDEO_TOLERANCE
    if src_dur is None or out_dur is None:
        checks.append(Check("duration", False, "ffprobe could not read a duration"))
    else:
        delta = abs(src_dur - out_dur)
        checks.append(
            Check(
                "duration",
                delta <= tolerance,
                f"source {src_dur:.2f}s output {out_dur:.2f}s",
            )
        )
    if output.endswith(".flac"):  # R-MUSIC: native integrity test on top of the decode
        checks.append(await _flac_test(output))
    if expected_chapters is not None:  # R-BOOK-2
        checks.append(await _chapter_check(output, expected_chapters))
    digest = await asyncio.to_thread(sha256_file, output)
    checks.append(Check("sha256", True, digest))
    failed = next((c for c in checks if not c.passed), None)
    return [asdict(c) for c in checks], digest, REASONS[failed.name] if failed else None


async def verify_ebook(output: str):
    """EPUBs must pass epubcheck (skipped, with a note, where it is not installed)."""
    from pathlib import Path

    from app.media.ebook import epubcheck

    checks = []
    if output.endswith(".epub"):
        ok, detail = await epubcheck(Path(output))
        checks.append(Check("epubcheck", ok is not False, detail))
    digest = await asyncio.to_thread(sha256_file, output)
    checks.append(Check("sha256", True, digest))
    failed = next((c for c in checks if not c.passed), None)
    return [asdict(c) for c in checks], digest, REASONS[failed.name] if failed else None
